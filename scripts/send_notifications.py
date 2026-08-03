#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""便携通知发送器 —— 把本期岗位变化摘要 + Excel 报告通过 邮件 / 企业微信 发出。

纯标准库（smtplib / email / urllib），不依赖任何 AI 工具或第三方包。
目的：让"推送"能力跟着仓库走，而不是绑死在某一家的运行时里
（与 WorkBuddy 自动化外推互补，二者可并存）。

配置（环境变量；可放在项目根目录的 `.env`（不进仓库，分享包未含需自行创建）：
  SMTP_HOST       SMTP 服务器，如 smtp.qq.com
  SMTP_PORT       SMTP 端口，如 465（SSL）或 587（STARTTLS）
  SMTP_USER       登录账号
  SMTP_PASS       授权码 / 密码
  FROM_EMAIL      发件人（默认同 SMTP_USER）
  TO_EMAIL        收件人，多个用逗号分隔
  WECHAT_WEBHOOK   企业微信群机器人 Webhook 地址

用法：
  # 仅校验配置与生成摘要，不真正发送
  python send_notifications.py --report reports/report-2026-08-01.xlsx \
      --new-jobs new_jobs.json --channel email --dry-run

  # 邮件（带 Excel 附件）+ 企业微信同时发
  python send_notifications.py --report reports/report-2026-08-01.xlsx \
      --new-jobs new_jobs.json --channel all

  # 只发企业微信（纯文本摘要，无法带附件，可在正文放报告路径 / 链接）
  python send_notifications.py --new-jobs new_jobs.json --channel wechat

摘要内容由 new_jobs.json 自动统计（新增 / 更新 / 重开 / 疑似下架 + 匹配度分布）。
"""
import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def _load_dotenv(path=None):
    """极简 .env 加载（纯标准库）：把 KEY=VALUE 写入 os.environ，不覆盖已有变量。"""
    candidates = []
    if path:
        candidates.append(path)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "..", ".env"))
    candidates.append(os.path.join(os.getcwd(), ".env"))
    for p in candidates:
        if p and os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            break  # 只加载第一个找到的 .env


_load_dotenv()
EVENT_LABEL = {
    "new": "🆕 新增",
    "updated": "🔄 更新",
    "reopened": "♻️ 重开",
    "possibly_closed": "⚠️ 疑似下架",
}
LEVEL_LABEL = {"green": "🟢高度匹配", "yellow": "🟡基本匹配", "red": "🟠可以尝试"}


def build_summary(new_jobs_path):
    """从 new_jobs.json 生成纯文本摘要。"""
    try:
        with open(new_jobs_path, encoding="utf-8") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        return "（未提供 new_jobs.json，无变化摘要）"
    if isinstance(jobs, dict):
        jobs = jobs.get("jobs", [])

    cnt = {"new": 0, "updated": 0, "reopened": 0, "possibly_closed": 0}
    lvl = {"green": 0, "yellow": 0, "red": 0}
    for j in jobs:
        ev = j.get("_event", "new")
        cnt[ev] = cnt.get(ev, 0) + 1
        lv = (j.get("level") or "yellow").lower()
        if lv in lvl:
            lvl[lv] += 1

    lines = ["【岗位雷达 · 本期变化摘要】"]
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(
        f"新增 {cnt['new']} · 更新 {cnt['updated']} · 重开 {cnt['reopened']} "
        f"· 疑似下架 {cnt['possibly_closed']}（合计 {len(jobs)}）"
    )
    lines.append(
        f"匹配度：🟢{lvl['green']} · 🟡{lvl['yellow']} · 🟠{lvl['red']}"
    )
    # 列出高度匹配的新增 / 更新岗位标题，方便一眼看到重点
    highlights = [
        j for j in jobs
        if (j.get("level") or "yellow").lower() == "green"
        and j.get("_event", "new") in ("new", "updated", "reopened")
    ]
    if highlights:
        lines.append("—— 高度匹配重点岗位 ——")
        for j in highlights[:15]:
            lines.append(
                f"  {EVENT_LABEL.get(j.get('_event','new'),'🆕')} "
                f"{j.get('company','')} · {j.get('title','')}（{j.get('city','')}）"
            )
    return "\n".join(lines)


def send_email(summary, report_path, dry_run):
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    to = os.environ.get("TO_EMAIL", "")
    frm = os.environ.get("FROM_EMAIL") or user
    port = int(os.environ.get("SMTP_PORT", "465"))

    if not (host and user and pwd and to):
        print("⚠️ 邮件配置不完整（需要 SMTP_HOST/SMTP_USER/SMTP_PASS/TO_EMAIL），跳过邮件发送。")
        return False
    recipients = [t.strip() for t in to.split(",") if t.strip()]

    msg = MIMEMultipart()
    msg["Subject"] = f"岗位雷达 · 本期变化摘要（{datetime.now().strftime('%Y-%m-%d')}）"
    msg["From"] = frm
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(summary, "plain", "utf-8"))

    if report_path and os.path.exists(report_path):
        with open(report_path, "rb") as f:
            part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(report_path)}"',
        )
        msg.attach(part)

    if dry_run:
        print(f"[dry-run] 邮件将发往：{recipients}（主题：{msg['Subject']}，"
              f"附件：{os.path.basename(report_path) if report_path else '无'}）")
        return True

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as s:
            s.login(user, pwd)
            s.sendmail(frm, recipients, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=context)
            s.login(user, pwd)
            s.sendmail(frm, recipients, msg.as_string())
    print(f"✅ 邮件已发送至：{recipients}")
    return True


def send_wechat(summary, dry_run):
    webhook = os.environ.get("WECHAT_WEBHOOK")
    if not webhook:
        print("⚠️ 未配置 WECHAT_WEBHOOK，跳过企业微信发送。")
        return False
    payload = json.dumps(
        {"msgtype": "markdown", "markdown": {"content": summary}}
    ).encode("utf-8")
    if dry_run:
        print(f"[dry-run] 企业微信将推送消息（{len(summary)} 字摘要）。")
        return True
    req = urllib.request.Request(
        webhook, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
        print(f"✅ 企业微信推送完成：{body}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"❌ 企业微信推送失败：{e}")
        return False


def main():
    p = argparse.ArgumentParser(description="岗位变化通知发送器（邮件 / 企业微信）")
    p.add_argument("--report", help="Excel 报告路径（作为邮件附件）")
    p.add_argument("--new-jobs", default="new_jobs.json", help="去重后变化岗位 JSON")
    p.add_argument("--channel", choices=["email", "wechat", "all"], default="all")
    p.add_argument("--dry-run", action="store_true", help="仅校验配置与生成摘要，不发送")
    args = p.parse_args()

    summary = build_summary(args.new_jobs)
    print("—— 本期摘要 ——")
    print(summary)
    print("—— 发送 ——")

    if args.channel in ("email", "all"):
        send_email(summary, args.report, args.dry_run)
    if args.channel in ("wechat", "all"):
        send_wechat(summary, args.dry_run)

    if args.dry_run:
        print("\n[dry-run 完成] 未实际发送。配置就绪后去掉 --dry-run 即可。")
    else:
        print("\n通知发送流程结束。")


if __name__ == "__main__":
    main()
