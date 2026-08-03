#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""质检后清洗：移除已确认下架(DEAD)岗位，将截止日已过者降级为 red。"""
import json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "jobs_raw.json")

# 质检 subagent 确认下线的链接片段
DEAD_FRAGMENTS = [
    "inn_izpnzl04alxp",   # 小红书 Skills社区(已下线)
    "inn_nbeg0swo4yix",   # 字节 抖音生活服务(已下线)
    "inn_lhhctwwwjnba",   # MiniMax 视频图像生成(已下线)
    "inn_xlpmtygxeqlv",   # MiniMax A28406(已下线)
    "inn_qcwvz18rt6lo",   # 元狲科技(已下线)
    "inn_9dvo2zacmdle",   # 字节 抖音社交AI互动(已下线)
]

with open(RAW, encoding="utf-8") as f:
    jobs = json.load(f)

kept, removed = [], []
for j in jobs:
    link = j.get("link", "")
    if any(frag in link for frag in DEAD_FRAGMENTS):
        removed.append(j["title"])
        continue
    # 截止日已过的 UNCLEAR 项：降级为 red 并标注
    if "inn_zrnaxonyqop3" in link:
        j["level"] = "red"
        j["notes"] = "质检提示：职位截止2026-05-11已过，投递前请确认是否仍招"
        j.setdefault("match_points", "")
        j["match_points"] += "（质检提示：截止日2026-05-11已过，需确认）"
    kept.append(j)

with open(RAW, "w", encoding="utf-8") as f:
    json.dump(kept, f, ensure_ascii=False, indent=2)

print(f"保留 {len(kept)} 条，移除 {len(removed)} 条已下架：")
for t in removed:
    print("  -", t)
