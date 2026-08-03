#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键入口：把"问答 → 验活 → 去重 → 报告"串起来。

流程：
  1) 没有 prefs.json   → 先跑 brief.py 收集需求，然后等人把 AI 返回的 JSON 准备好
  2) 没有 jobs_raw.json → 提示：把 prompt.txt 发给 AI，返回 JSON 存为 jobs_raw.json
  3) **验活门禁**       → 未验活 / 验活过期 / 仍有死链未清理 → 拒绝出报告
  4) 门禁通过           → jobstore 去重 → 生成 reports/report-*.xlsx 与 .html

为什么有第 3 步（血泪教训）
--------------------------
曾经把链接验活完全交给 AI 的提示词约束，AI 只验了 🟢、升级岗位后又没补验活，
用户随手点开报告里一条就是「职位已下架」，整份报告的可信度当场崩塌。
**提示词会被偷懒绕过，门禁不会。** 未验活的数据，这里根本走不到报告环节。

用法：
  python run.py             # 带门禁（未验活会拦下并告诉你怎么做）
  python run.py --verify    # 一条龙：自动验活 → 清洗 → 去重 → 报告（推荐）
  python run.py --skip-verify   # 强行跳过门禁，报告会打上醒目「未验活」水印

任何人只要会"回答问题 + 把一段文字发给 AI + 保存一个文件"就能用，零配置。
"""
import argparse
import json
import os
import subprocess
import sys

for _s in ("stdout", "stderr"):
    _f = getattr(sys, _s, None)
    if _f is not None and hasattr(_f, "reconfigure"):
        try:
            _f.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")


def resolve_data_home():
    """数据目录解析优先级：JOBRADAR_HOME 环境变量 > brief.py 写下的 .jobradar_home 标记 > 默认 ~/.job-radar"""
    env = os.environ.get("JOBRADAR_HOME")
    if env:
        return env
    marker = os.path.join(ROOT, ".jobradar_home")
    if os.path.isfile(marker):
        try:
            with open(marker, encoding="utf-8") as f:
                d = f.read().strip()
                if d:
                    return d
        except Exception:
            pass
    return os.path.expanduser("~/.job-radar")


# 用户数据外移到 skill 之外（可用 JOBRADAR_HOME 覆盖），重装/分享不丢数据
DATA_HOME = resolve_data_home()
PREFS = os.path.join(DATA_HOME, "prefs.json")
PROMPT = os.path.join(DATA_HOME, "prompt.txt")
RAW = os.path.join(DATA_HOME, "jobs_raw.json")
NEW = os.path.join(DATA_HOME, "new_jobs.json")
JOBSTORE = os.path.join(SCRIPTS, "jobstore.py")
BRIEF = os.path.join(SCRIPTS, "brief.py")
REPORT = os.path.join(SCRIPTS, "report.py")
VERIFY = os.path.join(SCRIPTS, "verify_links.py")


def py():
    return sys.executable or "python3"


def verify_gate(auto_verify=False, skip=False, allow_unknown=False):
    """出报告前的验活门禁。返回 True 放行，False 拦截。"""
    if skip:
        print("\n" + "!" * 66)
        print("⚠️  已跳过验活门禁（--skip-verify）。报告将打上「未验活」水印。")
        print("    报告里每一条链接用户都可能点开，死链会让整份报告失去可信度。")
        print("!" * 66 + "\n")
        os.environ["JOBRADAR_UNVERIFIED"] = "1"
        return True

    if auto_verify:
        print("\n【验活】正在逐条检查岗位链接是否仍在招…（--verify）")
        r = subprocess.run([py(), VERIFY, "--apply", "--in", RAW])
        if r.returncode != 0:
            print("❌ 验活脚本执行失败，已中止。")
            return False

    cmd = [py(), VERIFY, "--check", "--in", RAW]
    if allow_unknown:
        cmd.append("--allow-unknown")
        # 子进程设的环境变量传不回来，这里由父进程自己打标记供 report 打水印
        os.environ["JOBRADAR_L2_PENDING"] = "1"
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    print((r.stdout or "").rstrip())
    if r.stderr:
        print(r.stderr.rstrip())
    if r.returncode != 0:
        print("\n" + "=" * 66)
        print("🚫 报告生成已中止：数据未通过链接验活。")
        print("   一条死链就能毁掉整份报告的可信度，所以这里不放行。")
        print("\n   请任选其一：")
        print("     python scripts/run.py --verify        ← 推荐，自动验活后继续出报告")
        print("     python scripts/verify_links.py --apply  ← 单独验活，之后再跑 run.py")
        print("     python scripts/run.py --allow-unknown ← 强反爬平台的 unknown 无法做L2时放行（打水印）")
        print("     python scripts/run.py --skip-verify   ← 明知有风险仍要出（会打水印）")
        print("=" * 66)
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="岗位雷达一键入口：验活 → 去重 → 报告")
    ap.add_argument("--verify", action="store_true",
                    help="出报告前自动跑一遍链接验活并清洗（推荐）")
    ap.add_argument("--skip-verify", action="store_true",
                    help="跳过验活门禁（报告会打上未验活水印，不推荐）")
    ap.add_argument("--allow-unknown", action="store_true",
                    help="放行未经 AI 二层验活的 unknown 链接（报告会打未确证水印）")
    args = ap.parse_args()

    # 步骤 1：还没定义需求
    if not os.path.exists(PREFS):
        print("【步骤 1/4】先设置检索需求（中文问答，约 1 分钟）…\n")
        subprocess.run([py(), BRIEF], check=True)
        return

    # 步骤 2：需求有了，但还没拿到 AI 返回的岗位
    if not os.path.exists(RAW):
        print("\n【步骤 2/4】需求已就绪，还差 AI 返回的岗位数据。")
        print("  1) 打开 prompt.txt，把里面的内容完整发给你的 AI 助手")
        print("     （任意 AI 助手均可）。")
        print("  2) AI 会返回一段岗位 JSON，把那段 JSON 复制保存为：")
        print(f"     {RAW}")
        print("  3) 保存后重新运行：  python run.py\n")
        if os.path.exists(PROMPT):
            print("  （prompt.txt 已存在，直接打开使用即可）")
        return

    # 步骤 3：验活门禁（未验活的数据走不到报告环节）
    print("\n【步骤 3/4】链接验活门禁检查…")
    if not verify_gate(auto_verify=args.verify, skip=args.skip_verify,
                       allow_unknown=args.allow_unknown):
        sys.exit(2)

    # 步骤 4：去重 + 报告
    print("\n【步骤 4/4】正在去重并生成报告…")
    with open(RAW, encoding="utf-8") as f:
        raw_text = f.read()
    proc = subprocess.run(
        [py(), JOBSTORE, "filter"],
        input=raw_text, capture_output=True, text=True, encoding="utf-8",
    )
    if proc.stderr:
        print(proc.stderr.strip())
    if proc.returncode != 0:
        print("❌ 去重脚本出错：")
        print(proc.stdout)
        sys.exit(1)

    new_jobs = json.loads(proc.stdout)
    with open(NEW, "w", encoding="utf-8") as f:
        json.dump(new_jobs, f, ensure_ascii=False, indent=2)

    subprocess.run([py(), REPORT, NEW], check=True)
    print(f"\n✅ 完成。打开输出目录（{os.path.join(DATA_HOME, 'reports')}）下的 HTML 文件即可查看今日新增岗位。")


if __name__ == "__main__":
    main()
