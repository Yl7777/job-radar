#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互式问答 —— 让不懂代码的人也能"零配置文件"定义想搜什么。

运行：python brief.py
会生成：
  prefs.json   结构化检索需求（机器读）
  prompt.txt   一段可直接发给任意 AI 助手的检索指令

设计目标：不编辑任何文件、不装任何依赖，纯标准库 + 中文问答。

本次采集内容：
  0) 数据保存路径（默认 ~/.job-radar，可改为任意绝对路径；后续脚本自动沿用）
  1) 简历（核心输入）：文件 / 直接粘贴文本 / 无简历则口述背景
  2) 求职类型（实习/校招/社招）
  3) 目标城市
  4) 岗位方向/关键词
  5) 硬性要求（薪资/双休/大厂等）
  6) 出勤天数（实习必填）、实习时长（实习必填）、最早到岗时间
  7) 检索平台（多选；登录墙平台标注「需手动复核」，同样直接 site: 搜，不登录）
"""
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_data_home():
    """数据目录解析优先级：
    1) 环境变量 JOBRADAR_HOME（自动化 / 高级用户显式指定，最高优先级）
    2) brief.py 写下的标记文件 <skill根>/.jobradar_home（记录用户首次问答选的保存路径）
    3) 默认 ~/.job-radar
    保证「首次问答选的路径」在后续 run.py / jobstore.py / report.py 自动沿用。
    """
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


def ask_save_path(default_home):
    """第一次问答时询问数据保存路径（默认 ~/.job-radar，可改为任意绝对路径）。"""
    print("\n【第零步：数据保存路径】")
    print("  所有检索结果、去重库、报告都会存到这个文件夹。")
    print(f"  默认位置：{default_home}")
    print("  想存到自己的文件夹（如 D:/岗位雷达）？直接填绝对路径；")
    print("  留空 = 用默认位置。")
    while True:
        raw = input("  > ").strip()
        if not raw:
            return default_home
        path = os.path.abspath(os.path.expanduser(raw))
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            print(f"  ❌ 无法创建该路径：{e}，请换一个。")
            continue
        return path


# 用户数据外移到 skill 之外（可用 JOBRADAR_HOME 覆盖），重装/分享不丢数据
DATA_HOME = resolve_data_home()

JOB_TYPES = ["实习", "校招", "社招"]
HARD_FILTERS = ["双休/不加班", "大厂/上市公司", "外企优先", "支持远程", "无特别要求"]
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉",
          "西安", "苏州", "天津", "重庆", "远程优先"]

# 检索平台清单（名称, 类型标签）。所有平台均直接 site: 公开快照检索，无登录流程。
# 标签仅用于展示与"需手动复核"分组：「免登录」= 可验活；「登录墙」= 登录墙平台，结果标需手动复核。
PLATFORMS = [
    ("实习僧联盟站(rc114)", "免登录"),
    ("应届生求职网", "免登录"),
    ("牛客校招/内推", "免登录"),
    ("海投网", "免登录"),
    ("刺猬实习", "免登录"),
    ("国聘/24365/高校就业网", "免登录"),
    ("大厂官方招聘官网", "免登录"),
    ("中小厂/AI公司/出海官网", "免登录"),
    ("看准网(口碑)", "免登录"),
    ("微信公众号招聘推文", "免登录"),
    ("V2EX/掘金社区", "免登录"),
    ("BOSS直聘", "登录墙"),
    ("猎聘", "登录墙"),
    ("智联招聘", "登录墙"),
    ("前程无忧51job", "登录墙"),
    ("脉脉/内推", "登录墙"),
]

# 紧凑版平台说明（嵌入 prompt，使其自包含）
PLATFORMS_TEXT = """- 免登录（WebSearch 直接可搜，可验活）：实习僧联盟站(league.rc114.com)、应届生求职网、牛客校招/内推、
  海投网、刺猬实习、国聘/24365/高校就业网、大厂与 AI 公司官网、看准网、微信公众号招聘推文、V2EX/掘金
- 登录墙平台（同样直接 `site:` 公开快照检索，不登录、不要求先登录；结果标「⚠️ 需手动复核」并附再检索线索）：
  BOSS直聘、猎聘、智联、前程无忧51job、脉脉（详见 references/recheck-platforms.md）"""

SCHEMA = """[
  {
    "title": "岗位名称",
    "company": "公司名",
    "city": "工作城市",
    "salary": "薪资(如 200-300/天 或 15-25K)",
    "exp": "经验要求",
    "posted": "发布时间(如 3天前)",
    "level": "green | yellow | red  (绿=高度匹配, 黄=可投, 红=不太匹配)",
    "match_points": "匹配点简述",
    "tags": "标签,逗号分隔",
    "source": "来源平台",
    "link": "岗位原始链接(必须真实可打开的 URL)",
    "description": "岗位职责与要求(尽量详细, 用于去重与判断)",
    "job_type": "实习 | 校招 | 社招"
  }
]"""


def ask_multi(label, options, allow_custom=False, default_all=False):
    """多选问答：打印编号菜单，返回选中的字符串列表。"""
    print(f"\n{label}")
    for i, o in enumerate(options, 1):
        print(f"  {i}. {o}")
    if allow_custom:
        print(f"  {len(options)+1}. 其它(自行输入，多个用空格分隔)")
    hint = "可多选，输入编号(空格分隔)，回车=" + \
        ("全选" if default_all else "跳过") if (default_all or allow_custom) else \
        "可多选，输入编号(空格分隔)"
    raw = input("  > ").strip()
    if not raw:
        if default_all:
            return list(options)
        if allow_custom:
            return []
        return []
    custom_no = str(len(options) + 1)
    picks = []
    for tok in raw.replace(",", " ").split():
        if allow_custom and tok == custom_no:
            custom = input("  请输入自定义项(空格分隔)：").strip()
            picks.extend(custom.split())
        elif tok.isdigit():
            idx = int(tok) - 1
            if 0 <= idx < len(options):
                picks.append(options[idx])
    seen, out = set(), []
    for p in picks:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def ask_text(label, required=True):
    while True:
        val = input(f"\n{label}\n  > ").strip()
        if val or not required:
            return val
        print("  （此项不能为空，请填写）")


def main():
    print("=" * 56)
    print("  岗位雷达 · 检索需求设置（中文问答，无需改任何文件）")
    print("=" * 56)

    # ---- 0) 数据保存路径 ----
    global DATA_HOME
    DATA_HOME = ask_save_path(resolve_data_home())
    try:
        with open(os.path.join(ROOT, ".jobradar_home"), "w", encoding="utf-8") as f:
            f.write(DATA_HOME)
    except Exception:
        pass
    os.makedirs(DATA_HOME, exist_ok=True)

    # ---- 1) 简历：核心输入 ----
    print("\n【第一步：简历（核心输入）】")
    print("  有简历文件吗？输入文件路径（如 C:/resume.pdf），或直接粘贴简历文本；")
    print("  都没有就直接回车，改为口述背景。")
    resume_raw = input("  > ").strip()
    resume_path, resume_text = "", ""
    if resume_raw:
        if os.path.isfile(resume_raw):
            resume_path = os.path.abspath(resume_raw)
            print(f"  → 已记录简历文件：{resume_path}（AI 会读取它提取画像）")
        else:
            resume_text = resume_raw
            print("  → 已记录粘贴的简历文本")
    else:
        print("  → 无简历，将在最后口述背景。")

    # ---- 2) 求职类型 ----
    job_types = ask_multi("你找哪类机会？（多选）", JOB_TYPES, default_all=False)
    if not job_types:
        job_types = ["实习"]
        print("  → 默认：实习")

    # ---- 3) 城市 ----
    cities = ask_multi("目标城市？（多选，可选「其它」自填）", CITIES,
                       allow_custom=True, default_all=False)

    # ---- 4) 方向 ----
    keywords = ask_text("岗位方向/关键词？（如：AI产品运营、后端开发 Go、用户增长）")

    # ---- 5) 硬性要求 ----
    hard = ask_multi("硬性要求？（多选）", HARD_FILTERS, default_all=False)

    # ---- 6) 出勤天数 / 实习时长 / 最早到岗时间 ----
    min_days, duration_months, start_date = "", "", ""
    if "实习" in job_types:
        raw = input("\n实习每周至少能出勤几天？（直接回车=不限制）\n  > ").strip()
        if raw.isdigit():
            min_days = int(raw)
        raw = input("\n至少能连续实习几个月？（直接回车=不限制）\n  > ").strip()
        if raw.isdigit():
            duration_months = int(raw)
    raw = input("\n最早到岗时间？（如 立即 / 一周内 / 9月初 / 下学期开始后，回车=未限定）\n  > ").strip()
    if raw:
        start_date = raw

    # ---- 7) 检索平台（多选）----
    plat_labels = [f"{p}（{tag}）" for p, tag in PLATFORMS]
    plat_names = [p for p, _ in PLATFORMS]
    print("\n【第六步：检索平台（多选）】")
    print("  所有平台都直接 site: 公开快照检索；标注「登录墙」的平台结果会标「⚠️ 需手动复核」，")
    print("  由你在自己已登录的 App 内确认在招与投递。无需先登录。")
    selected = ask_multi(
        "要搜哪些平台？（编号见上）",
        plat_labels, default_all=False)
    # 还原为平台名
    selected_names = []
    for s in selected:
        name = s.split("（")[0]
        if name in plat_names:
            selected_names.append(name)
    login_selected = [n for n, t in PLATFORMS if n in selected_names and t == "登录墙"]
    free_selected = [n for n, t in PLATFORMS if n in selected_names and t == "免登录"]

    # ---- 无简历则口述 ----
    background = ""
    if not resume_path and not resume_text:
        background = ask_text(
            "请简单口述背景（职业方向/经验年限/擅长技能/学校专业，回车=跳过）",
            required=False)

    prefs = {
        "resume_path": resume_path,
        "resume_text": resume_text,
        "job_types": job_types,
        "cities": cities,
        "keywords": keywords,
        "hard_filters": hard,
        "platforms": selected_names,
        "platforms_walled": login_selected,
        "platforms_free": free_selected,
        "min_days_per_week": min_days,
        "duration_months": duration_months,
        "start_date": start_date,
        "background": background,
        "data_dir": DATA_HOME,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(os.path.join(DATA_HOME, "prefs.json"), "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)

    # ---- 生成可直接发给任意 AI 的检索 prompt ----
    hard_line = "、".join(hard) if hard and "无特别要求" not in hard else "无特别要求"
    if resume_path:
        resume_block = f"【候选人简历】请先读取并解析以下简历文件，提取目标方向、核心技能、经验年限、硬性要求等画像，再据此检索与打分：\n  {resume_path}"
    elif resume_text:
        resume_block = f"【候选人简历】\n{resume_text}"
    else:
        resume_block = f"【候选人画像（无简历，口述）】{background or '用户未提供，请按方向/关键词合理推断，打分保守些'}"

    recheck_note = (
        "【登录墙平台·需手动复核】本次包含登录墙平台：" + "、".join(login_selected) +
        "。这些平台**直接 `site:` 公开快照检索即可，不登录、不处理 cookies**；"
        "搜到的岗位标 `needs_recheck=true`，并填全再检索线索（岗位名/帖子标题/作者/发送时间/来源），"
        "由用户在对应 App 内确认在招与投递。详见 references/recheck-platforms.md。"
    ) if login_selected else "【登录墙平台】本次未选登录墙平台，全部为免登录可验活来源。"

    prompt = f"""你是一个求职检索助手。请根据下面的检索需求，在中国大陆招聘平台搜索真实在招的岗位，并返回 JSON 数组。

【检索需求】
- 机会类型：{ "、".join(job_types) }
- 目标城市：{ "、".join(cities) if cities else "全国" }
- 岗位方向/关键词：{keywords}
- 硬性要求：{hard_line}
{ f"- 实习每周至少出勤：{min_days} 天" if min_days else "" }
{ f"- 实习时长至少：{duration_months} 个月" if duration_months else "" }
{ f"- 最早到岗时间：{start_date}" if start_date else "" }
- 本次检索平台：{ "、".join(selected_names) if selected_names else "（由你按方向自由选择免登录平台）" }

{resume_block}

【搜索范围（中国大陆）】
{PLATFORMS_TEXT}
（更完整的平台与语法见 references/platforms-cn.md；企业官网与各高校就业网质量最高，优先纳入）

【质量要求】
1. 宁多勿少、全面、真实：尽量覆盖多家平台，给出真实可打开的岗位链接。
2. 幻觉要低：不要编造岗位；不确定的字段填空字符串 ""，不要编造薪资/公司。
3. 匹配度：针对用户方向判断 level（green=高度匹配 / yellow=可投 / red=不太匹配）。
4. 时效强制：每组搜索追加时间限定 `after:<30天前的日期>`，过滤过期快照；
   看不到日期信号的岗位标注 posted 为 "⏳时效未确认"。
5. 链接真实性：🟢 高度匹配岗位必须访问链接确认仍在招（并行验证），
   页面出现"职位已下线/已停止招聘/404"等下架信号的移除或降级。

{recheck_note}

【输出格式】只输出如下 JSON 数组，不要额外解释文字：
{SCHEMA}

示例一条：
{{"title":"AI产品运营实习生","company":"字节跳动","city":"上海","salary":"200-300/天","exp":"在校","posted":"2天前","level":"green","match_points":"方向高度契合","tags":"实习,AI","source":"牛客","link":"https://...","description":"负责AI功能需求分析与迭代","job_type":"实习"}}

完成后请将整段 JSON 保存到 jobs_raw.json，并运行 `python scripts/run.py` 生成 Excel 与 HTML 报告。
"""

    with open(os.path.join(DATA_HOME, "prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt)

    print("\n✅ 已生成：")
    print(f"   prefs.json  （检索需求，机器读）")
    print(f"   prompt.txt  （检索指令，下一步发给 AI）")
    print(f"   📁 数据保存位置：{DATA_HOME}")
    print(f"      （去重库、报告都会存这里；后续脚本会自动沿用此路径）")
    if login_selected:
        print(f"   ⚠ 你选了登录墙平台：{', '.join(login_selected)} —— 结果会标「需手动复核」，投前请 App 内确认。")
    print("\n👉 下一步：把 prompt.txt 的完整内容发给你的 AI 助手，")
    print("   让它返回岗位 JSON（或自行抓取），把那段 JSON 保存为")
    print("   jobs_raw.json，然后运行：  python run.py")
    print("   （run.py 会自动去重，并生成 Excel 表格 + HTML 报告。）")


if __name__ == "__main__":
    main()
