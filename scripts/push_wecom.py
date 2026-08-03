#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""企业微信群机器人纯文本推送器。

把纯文本日报（或提醒）分片推送到企业微信群机器人 Webhook。
纯标准库（urllib / json / re），不依赖任何第三方包，跟仓库一起走。

Webhook 来源优先级：
  --webhook  >  环境变量 WECHAT_WEBHOOK  >  --config 文件（可选，指向任意含 webhook 的配置文件）自动解析

注意：企业微信 text 类型单条上限 2048 字节，本脚本按 1900 字节分片，
优先在换行处断开，确保长日报也能完整送达，且裸 URL 在企业微信里可点击。

用法：
  # 推送文件内容（webhook 从 --config 指定的配置文件解析，可选）
  python push_wecom.py --text reports/push-2026-08-02.txt --config path/to/push-config.md

  # 直接指定 webhook（测试用）
  python push_wecom.py --text reports/push-2026-08-02.txt \
      --webhook "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx"

  # 从标准输入
  cat daily.txt | python push_wecom.py --stdin --config path/to/push-config.md

  # 仅校验不发送
  python push_wecom.py --text daily.txt --config path/to/push-config.md --dry-run
"""
import argparse
import json
import os
import re
import sys
import urllib.request


def parse_webhook_from_config(config_path):
    """从 push-config.md 解析企业微信 webhook 链接。"""
    if not config_path or not os.path.exists(config_path):
        return None
    try:
        with open(config_path, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return None
    m = re.search(r"https://qyapi\.weixin\.qq\.com/[^\s\"'）)）>]+", text)
    if m:
        return m.group(0).rstrip("。，,；;")
    return None


def split_text(text, limit=1900):
    """按字节上限分片，优先在换行处断开，避免截断中文。"""
    chunks = []
    cur = ""
    for line in text.split("\n"):
        candidate = (cur + "\n" + line) if cur else line
        if len(candidate.encode("utf-8")) > limit and cur:
            chunks.append(cur)
            cur = line
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks


def send_chunk(webhook, content, msgtype, dry_run):
    if dry_run:
        print(f"[dry-run] 将推送 {len(content.encode('utf-8'))} 字节（类型 {msgtype}）")
        return True
    payload = json.dumps({"msgtype": msgtype, msgtype: {"content": content}}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
        print(f"✅ 推送成功：{body}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"❌ 推送失败：{e}")
        return False


def main():
    p = argparse.ArgumentParser(description="企业微信群机器人纯文本推送器")
    p.add_argument("--text", help="纯文本日报 / 提醒文件路径")
    p.add_argument("--stdin", action="store_true", help="从标准输入读取")
    p.add_argument("--config", help="push-config.md 路径（自动解析 webhook）")
    p.add_argument("--webhook", help="直接指定 webhook（覆盖 config/环境变量）")
    p.add_argument("--type", choices=["text", "markdown"], default="text")
    p.add_argument("--dry-run", action="store_true", help="仅校验，不发送")
    args = p.parse_args()

    if args.stdin:
        text = sys.stdin.read()
    elif args.text:
        if not os.path.exists(args.text):
            print(f"❌ 文件不存在：{args.text}")
            sys.exit(1)
        with open(args.text, encoding="utf-8") as f:
            text = f.read()
    else:
        print("❌ 必须提供 --text 或 --stdin")
        sys.exit(1)

    webhook = args.webhook or os.environ.get("WECHAT_WEBHOOK") or parse_webhook_from_config(args.config)
    if not webhook:
        print("⚠️ 未找到企业微信 webhook（--webhook / WECHAT_WEBHOOK / --config 均未提供）。跳过推送。")
        sys.exit(0)  # 未配置不阻塞上游任务

    chunks = split_text(text)
    print(f"—— 分片 {len(chunks)} 条，逐片推送（类型 {args.type}） ——")
    ok = True
    for i, c in enumerate(chunks, 1):
        print(f"[片 {i}/{len(chunks)}] {len(c.encode('utf-8'))} 字节")
        if not send_chunk(webhook, c, args.type, args.dry_run):
            ok = False
    print("\n推送流程结束。" if ok else "\n推送存在失败，请检查 webhook。")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
