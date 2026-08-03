#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把去重后的"变化岗位"渲染成 本地 HTML 报告 与 Excel 表格（链接可点击）。

运行：python report.py [new_jobs.json]
默认读取 ROOT/new_jobs.json，输出：
  - ROOT/reports/report-YYYY-MM-DD.html
  - ROOT/reports/report-YYYY-MM-DD.xlsx
HTML 优先使用 templates/report.html；模板缺失时回退内置样式。
Excel 由纯标准库生成（zipfile + XML），零依赖、无需 openpyxl。

每条岗位带 "_event" 字段（new / updated / reopened / possibly_closed）。
报告分区：
  - 新增 / 更新 / 重开  → 按匹配度分组展示（🟢🟡🟠）
  - 疑似下架            → 单独警告区（浅红填充）

列定义对齐 references/excel-export.md。
"""
import json
import os
import sys
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


# 用户数据外移到 skill 之外，避免重装/分享时误删；可用 JOBRADAR_HOME 覆盖
DATA_HOME = resolve_data_home()
DEFAULT_IN = os.path.join(DATA_HOME, "new_jobs.json")
OUT_DIR = os.path.join(DATA_HOME, "reports")
TEMPLATE = os.path.join(ROOT, "templates", "report.html")

LEVEL_BADGE = {
    "green": ("#0F6E56", "高度匹配", "🟢"),
    "yellow": ("#BA7517", "可投递", "🟡"),
    "red": ("#A32D2D", "参考", "🔴"),
}
# Excel 三档展示名（与 SKILL 输出格式一致：🟢🟡🟠）
LEVEL_XLSX = {
    "green": "🟢高度匹配",
    "yellow": "🟡基本匹配",
    "red": "🟠可以尝试",
}
# Excel 行底色（绿/黄/橙/疑似下架浅红）
XLSX_FILL = {"green": "C6EFCE", "yellow": "FFEB9C", "red": "FFCC99", "closed": "FFC7CE"}

EVENT_BADGE = {
    "new": "🆕 新增",
    "updated": "🔄 更新",
    "reopened": "♻️ 重开",
    "possibly_closed": "⚠️ 疑似下架",
}

# 链接验活状态（由 scripts/verify_links.py 写入 verify_status 字段）
# 让用户在点开链接之前就知道这条靠不靠谱 —— 死链毁掉的是整份报告的信任
VERIFY_BADGE = {
    "alive": ("✅ 已验活", "#0F6E56"),
    "alive_l2": ("✅ AI已复核", "#0F6E56"),
    "unknown": ("⏳ 待核实", "#BA7517"),
    "unsure": ("❓ 无法确认", "#B4553A"),
    "not_detail": ("⚠️ 非详情页", "#A35A2D"),
    "dead": ("❌ 已下架", "#A32D2D"),
    "": ("— 未验活", "#888888"),
}
# 登录墙平台（BOSS/猎聘/智联/51job/脉脉等）公开快照检索得到的岗位：
# AI 无法确认在招，标记「需手动复核」，由用户在自己已登录的 App 内用再检索线索确认。
RECHECK_BADGE = ("⚠️ 需手动复核", "#B4553A")


def recheck_hint(job):
    """拼接登录墙平台岗位的『再检索线索』，供用户在对应 App 内自行确认在招与投递。

    字段来源：岗位名(title，必有) / 帖子标题(post_title) / 作者·发帖人(author) /
    发送时间(posted) / 来源平台(source)。采集时务必把能拿到的线索填全。
    """
    parts = []
    if job.get("title"):
        parts.append(f"岗位名：{job['title']}")
    if job.get("post_title"):
        parts.append(f"帖子标题：{job['post_title']}")
    if job.get("author"):
        parts.append(f"作者/发帖：{job['author']}")
    if job.get("posted"):
        parts.append(f"发送时间：{job['posted']}")
    if job.get("source"):
        parts.append(f"来源：{job['source']}")
    return "｜".join(parts)


# Excel 列顺序（含"变化"、"公司类型"与"验活"）
XLSX_COLS = [
    ("编号", "idx"),
    ("变化", "event_x"),
    ("匹配度", "level_x"),
    ("验活", "verify_x"),
    ("岗位名称", "title"),
    ("公司", "company"),
    ("公司类型", "company_tag"),
    ("城市", "city"),
    ("薪资", "salary"),
    ("经验要求", "exp"),
    ("发布日期", "posted"),
    ("匹配点", "match_points"),
    ("标签", "tags"),
    ("来源平台", "source"),
    ("链接", "link"),
    ("备注", "notes"),
]


def esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def level_of(job):
    lv = (job.get("level") or "yellow").lower()
    return lv if lv in LEVEL_BADGE else "yellow"


def event_of(job):
    return job.get("_event", "new")


def verify_of(job):
    """归一化验活状态，并把 AI 二层裁决的结果单独区分出来。

    脚本判 alive 与 AI 亲自打开确认，可信度不同；AI 也确认不了的（unsure）
    必须显式警示，不能混在 ⏳ 待核实里让用户误以为只是没验。
    """
    v = (job.get("verify_status") or "").lower()
    l2 = (job.get("l2_status") or "").lower()
    if l2 == "unsure":
        return "unsure"
    # L2 裁决本来就是针对 L1 判不了的 unknown 做的：重跑 L1 时脚本依旧看不穿
    # （反爬/登录墙/JS 渲染没变），verify_status 会再次落回 unknown。
    # 此时若要求 v == "alive" 才认 L2，AI 亲自打开确认过的结论就被 L1 重跑抹掉，
    # 报告把「✅ AI已复核」降级显示成「⏳ 待核实」（2026-08-02 实测复现）。
    if l2 == "alive" and v in ("alive", "unknown", ""):
        return "alive_l2"
    return v if v in VERIFY_BADGE else ""


# ----------------------------------------------------------------------------
# HTML 渲染
# ----------------------------------------------------------------------------
def render_html(jobs):
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    changes, closed = [], []
    for j in jobs:
        (closed if event_of(j) == "possibly_closed" else changes).append(j)

    groups = {"green": [], "yellow": [], "red": []}
    for j in changes:
        groups[level_of(j)].append(j)

    cards = []
    for lv in ("green", "yellow", "red"):
        for j in groups[lv]:
            color, label, icon = LEVEL_BADGE[lv]
            ev = EVENT_BADGE.get(event_of(j), "")
            link = esc(j.get("link") or "")
            tag = esc(j.get("company_tag") or "")
            link_html = f'<a href="{link}" target="_blank" rel="noopener">{esc(j.get("title"))}</a>' \
                if link else esc(j.get("title"))
            vlabel, vcolor = RECHECK_BADGE if j.get("needs_recheck") else VERIFY_BADGE[verify_of(j)]
            vtip = esc(j.get("verify_evidence") or "")
            row = f"""
      <div class="card {lv}" data-level="{lv}" data-city="{esc(j.get('city') or '')}" data-source="{esc(j.get('source') or '')}" style="border-left:4px solid {color}">
        <div class="head">
          <span class="badge" style="background:{color}">{icon} {label}</span>
          <span class="event">{ev}</span>
          <span class="verify" style="color:{vcolor};border-color:{vcolor}" title="{vtip}">{vlabel}</span>
          <span class="title">{link_html}</span>
        </div>
        <div class="meta">
          <span>🏢 {esc(j.get('company'))}{(' · ' + tag) if tag else ''}</span>
          <span>📍 {esc(j.get('city'))}</span>
          <span>💰 {esc(j.get('salary')) or '薪资面议'}</span>
          <span>📡 {esc(j.get('source'))}</span>
        </div>
        {f'<div class="match">匹配点：{esc(j.get("match_points"))}</div>' if j.get('match_points') else ''}
        {f'<div class="desc">{esc(j.get("description"))}</div>' if j.get('description') else ''}
        {f'<div class="recheck" style="font-size:12px;color:#8A4B00;background:#FFF4E5;border:1px solid #FFB74D;border-radius:8px;padding:8px 10px;margin-top:6px;line-height:1.6">⚠️ 需手动复核（登录墙平台，AI 无法确证在招）｜再检索线索：{esc(recheck_hint(j))}<br>请在该平台 App 内用以上信息确认在招并投递，勿直接相信本报告链接。</div>' if j.get('needs_recheck') else ''}
      </div>"""
            cards.append(row)

    # 疑似下架区
    closed_cards = []
    for j in closed:
        link = esc(j.get("link") or "")
        link_html = f'<a href="{link}" target="_blank" rel="noopener">{esc(j.get("title"))}</a>' \
            if link else esc(j.get("title"))
        closed_cards.append(f"""
      <div class="card closed" data-level="red" data-city="{esc(j.get('city') or '')}" data-source="{esc(j.get('source') or '')}">
        <div class="head">
          <span class="badge closed">⚠️ 疑似下架</span>
          <span class="title">{link_html}</span>
        </div>
        <div class="meta">
          <span>🏢 {esc(j.get('company'))}</span>
          <span>📍 {esc(j.get('city'))}</span>
          <span>📡 {esc(j.get('source'))}</span>
        </div>
      </div>""")

    total = len(jobs)
    if total == 0:
        body = '<p class="empty">本次没有检索到新增或变化的岗位。可能是平台暂无更新，或请把 AI 返回的 JSON 保存为 jobs_raw.json 后重试。</p>'
        closed_section = ""
    else:
        body = "".join(cards) if cards else '<p class="empty">本期无新增 / 更新 / 重开岗位。</p>'
        closed_section = (
            '<h2 class="closed-h">⚠️ 疑似下架（连续多次检索未出现，建议手动确认）</h2>'
            + "".join(closed_cards)
        ) if closed_cards else ""

    n_new = sum(1 for j in jobs if event_of(j) == "new")
    n_upd = sum(1 for j in jobs if event_of(j) == "updated")
    n_re = sum(1 for j in jobs if event_of(j) == "reopened")
    n_cls = len(closed)
    n_alive = sum(1 for j in jobs if verify_of(j) in ("alive", "alive_l2"))
    n_l2 = sum(1 for j in jobs if verify_of(j) == "alive_l2")
    n_unk = sum(1 for j in jobs if verify_of(j) == "unknown")
    n_unsure = sum(1 for j in jobs if verify_of(j) == "unsure")
    n_nd = sum(1 for j in jobs if verify_of(j) == "not_detail")
    n_unver = sum(1 for j in jobs if verify_of(j) == "")
    n_recheck = sum(1 for j in jobs if j.get("needs_recheck"))
    stats_html = (
        f'<span class="stat">🆕 新增 <b>{n_new}</b></span>\n'
        f'    <span class="stat">🔄 更新 <b>{n_upd}</b></span>\n'
        f'    <span class="stat">♻️ 重开 <b>{n_re}</b></span>\n'
        f'    <span class="stat">⚠️ 疑似下架 <b>{n_cls}</b></span>\n'
        f'    <span class="stat">🟢 高度 <b>{len(groups["green"])}</b></span>\n'
        f'    <span class="stat">🟡 可投递 <b>{len(groups["yellow"])}</b></span>\n'
        f'    <span class="stat">🔴 参考 <b>{len(groups["red"])}</b></span>\n'
        f'    <span class="stat">合计 <b>{total}</b></span>\n'
        f'    <span class="stat">🔗 链接验活：✅ <b>{n_alive}</b>'
        + (f'（AI复核 {n_l2}）' if n_l2 else '')
        + f' · ⏳ <b>{n_unk}</b> · ⚠️ <b>{n_nd}</b>'
        + (f' · ❓无法确认 <b>{n_unsure}</b>' if n_unsure else '')
        + (f' · 未验活 <b>{n_unver}</b>' if n_unver else '') + '</span>'
    )

    # 未验活/未确证水印：跳过门禁或含未裁决 unknown 的报告必须显著提示，
    # 不能让用户误以为链接都是活的 —— 这正是"点开显示职位已下架"的体验来源。
    banner = ""
    if os.environ.get("JOBRADAR_UNVERIFIED") == "1" or n_unver:
        banner = ('<div class="warnbar">⚠️ 本报告包含<b>未经链接验活</b>的岗位，'
                  '其中可能存在已下架职位。投递前请先点开链接确认，'
                  '或运行 <code>python scripts/verify_links.py --apply</code> 后重新生成。</div>')
    elif os.environ.get("JOBRADAR_L2_PENDING") or n_unk or n_unsure or n_recheck:
        _n = n_unk + n_unsure + n_recheck
        banner = (f'<div class="warnbar">⏳ 本报告有 <b>{_n}</b> 条岗位来自登录墙平台'
                  '（BOSS / 猎聘 / 智联 / 51job 等），AI <b>无法确证是否仍在招</b>，'
                  '已标「⚠️ 需手动复核」并附<b>再检索线索</b>（岗位名 / 帖子标题 / 作者 / 发送时间）。'
                  '请在该平台 App 内用这些信息确认在招并投递，不要直接相信本报告链接。</div>')

    filters_html = (
        '<div class="filters">'
        '<select id="f-city"><option value="">全部城市</option></select>'
        '<select id="f-source"><option value="">全部来源</option></select>'
        '<select id="f-level"><option value="">全部等级</option>'
        '<option value="green">🟢 高度匹配</option>'
        '<option value="yellow">🟡 基本匹配</option>'
        '<option value="red">🔴 参考 / 下架</option></select>'
        '</div>'
    )
    if os.path.exists(TEMPLATE):
        with open(TEMPLATE, encoding="utf-8") as f:
            tpl = f.read()
        html = (tpl.replace("{TITLE}", f"岗位雷达 · {date_str}")
                   .replace("{GENTIME}", today.strftime("%Y-%m-%d %H:%M"))
                   .replace("{STATS}", stats_html)
                   .replace("{FILTERS}", filters_html)
                   .replace("{BODY}", banner + body + closed_section))
    else:
        html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>岗位雷达 · {date_str}</title></head>
<body>
<h1>岗位雷达 · {date_str}</h1>
<div class="sub">生成时间 {today.strftime('%Y-%m-%d %H:%M')}</div>
<div>{stats_html}</div>
{banner}
{body}
{closed_section}
</body></html>"""
    return html, date_str


# ----------------------------------------------------------------------------
# Excel 渲染（纯标准库，零依赖）
# ----------------------------------------------------------------------------
def _col_letter(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _xml_col_widths():
    widths = [6, 12, 12, 13, 34, 20, 12, 12, 14, 12, 14, 30, 18, 14, 40, 18]
    cols = []
    for i, w in enumerate(widths, 1):
        cols.append(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>')
    return "<cols>" + "".join(cols) + "</cols>"


def _sheet_xml(jobs):
    header_fill = "1"   # blue
    # cellXf 索引：0 default, 1 header, 2 green, 3 yellow, 4 orange, 5 closed, 6 超链接
    fills = {"green": "2", "yellow": "3", "red": "4", "closed": "5"}
    link_style = "6"
    rows = []
    # 表头
    head_cells = []
    for i, (name, _) in enumerate(XLSX_COLS, 1):
        ref = f"{_col_letter(i)}1"
        head_cells.append(
            f'<c r="{ref}" s="{header_fill}" t="inlineStr"><is><t>{escape(name)}</t></is></c>')
    rows.append(f'<row r="1">{"".join(head_cells)}</row>')

    link_ci = next(i for i, (_, k) in enumerate(XLSX_COLS, 1) if k == "link")
    hyperlinks = []  # (cell_ref, url)
    for ridx, j in enumerate(jobs, start=2):
        lv = level_of(j)
        is_closed = event_of(j) == "possibly_closed"
        fill = "5" if is_closed else fills.get(lv, "0")
        cells = []
        for ci, (_, key) in enumerate(XLSX_COLS, 1):
            ref = f"{_col_letter(ci)}{ridx}"
            if key == "idx":
                val = str(ridx - 1)
            elif key == "event_x":
                val = EVENT_BADGE.get(event_of(j), "🆕 新增")
            elif key == "level_x":
                val = LEVEL_XLSX.get(lv, "")
            elif key == "verify_x":
                val = "⚠️ 需手动复核" if j.get("needs_recheck") else VERIFY_BADGE[verify_of(j)][0]
            elif key == "notes":
                val = j.get("notes") or ""
                if j.get("needs_recheck"):
                    hint = recheck_hint(j)
                    val = (val + " ｜" if val else "") + "【需手动复核】" + hint
            else:
                val = j.get(key) or ""
            val = escape(str(val))
            # 链接列：写入真实 OOXML 超链接（仅限 http/https，规避 javascript: 等危险协议）
            if key == "link":
                url = (j.get("link") or "").strip()
                if url.lower().startswith(("http://", "https://")):
                    hyperlinks.append((ref, url))
                    cells.append(
                        f'<c r="{ref}" s="{link_style}" t="inlineStr"><is><t>{escape(url)}</t></is></c>')
                    continue
            cells.append(
                f'<c r="{ref}" s="{fill}" t="inlineStr"><is><t>{val}</t></is></c>')
        rows.append(f'<row r="{ridx}">{"".join(cells)}</row>')

    ncols = len(XLSX_COLS)
    last_col = _col_letter(ncols)
    last_row = len(jobs) + 1
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        + _xml_col_widths()
        + f'<sheetData>{"".join(rows)}</sheetData>'
        f'<autoFilter ref="A1:{last_col}{last_row}"/>'
    )
    if hyperlinks:
        hl = "".join(
            f'<hyperlink ref="{ref}" r:id="rId{idx}"/>'
            for idx, (ref, _) in enumerate(hyperlinks, start=1)
        )
        sheet += f'<hyperlinks>{hl}</hyperlinks>'
    sheet += '</worksheet>'
    return sheet, hyperlinks


def _styles_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="3">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        '<font><u/><color rgb="FF0563C1"/><sz val="11"/><name val="Calibri"/></font>'
        '</fonts>'
        '<fills count="7">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF4472C4"/></patternFill></fill>'  # header blue
        '<fill><patternFill patternType="solid"><fgColor rgb="FFE8F5E9"/></patternFill></fill>'  # green
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF8E1"/></patternFill></fill>'  # yellow
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF3E0"/></patternFill></fill>'  # orange
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFFC7CE"/></patternFill></fill>'  # closed light red
        '</fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="7">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'                                  # 0 default
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'       # 1 header
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/>'                     # 2 green
        '<xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyFill="1"/>'                     # 3 yellow
        '<xf numFmtId="0" fontId="0" fillId="5" borderId="0" xfId="0" applyFill="1"/>'                     # 4 orange
        '<xf numFmtId="0" fontId="0" fillId="6" borderId="0" xfId="0" applyFill="1"/>'                     # 5 closed
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>'                     # 6 超链接(蓝色下划线)
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )


def write_xlsx(path, jobs):
    sheet_xml, hyperlinks = _sheet_xml(jobs)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument/spreadsheetml.styles+xml"/>'
    )
    if hyperlinks:
        content_types += ('<Override PartName="/xl/worksheets/_rels/sheet1.xml.rels" '
                          'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>')
    content_types += '</Types>'
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="岗位搜索结果" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", _styles_xml())
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        if hyperlinks:
            rel_items = "".join(
                f'<Relationship Id="rId{idx}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                f'Target="{escape(url)}" TargetMode="External"/>'
                for idx, (_, url) in enumerate(hyperlinks, start=1)
            )
            sheet_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + rel_items +
                '</Relationships>'
            )
            z.writestr("xl/worksheets/_rels/sheet1.xml.rels", sheet_rels)


# ----------------------------------------------------------------------------
def _safe_write(path, writer, max_try=20):
    """写文件；若目标被占用（用户正开着上一版 Excel）则自动换名，绝不让整条流水线崩掉。"""
    base, ext = os.path.splitext(path)
    for i in range(max_try):
        target = path if i == 0 else f"{base}-v{i + 1}{ext}"
        try:
            writer(target)
            if i:
                print(f"⚠️ {os.path.basename(path)} 被占用（可能正开着），已输出为 {os.path.basename(target)}")
            return target
        except PermissionError:
            continue
    raise PermissionError(f"无法写入 {path}：连续 {max_try} 个候选文件名均被占用，请关闭已打开的报告后重试。")


def main():
    inp = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    with open(inp, encoding="utf-8") as f:
        jobs = json.load(f)
    if isinstance(jobs, dict):
        jobs = jobs.get("jobs", [])
    os.makedirs(OUT_DIR, exist_ok=True)
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    # HTML
    html, _ = render_html(jobs)
    html_path = _safe_write(os.path.join(OUT_DIR, f"report-{date_str}.html"),
                            lambda p: open(p, "w", encoding="utf-8").write(html))

    # Excel
    xlsx_path = _safe_write(os.path.join(OUT_DIR, f"report-{date_str}.xlsx"),
                            lambda p: write_xlsx(p, jobs))

    n_new = sum(1 for j in jobs if event_of(j) == "new")
    n_cls = sum(1 for j in jobs if event_of(j) == "possibly_closed")
    print(f"已生成报告：{html_path}（共 {len(jobs)} 条变化：新增 {n_new} / 疑似下架 {n_cls}）")
    print(f"已生成表格：{xlsx_path}（链接可点击，三档配色 + 疑似下架浅红）")


if __name__ == "__main__":
    main()
