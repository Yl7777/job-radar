#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链接验活器 —— 岗位雷达的「防死链」闸门（纯标准库，零依赖）。

为什么有这个脚本
----------------
血泪教训：曾经把链接验活完全交给 AI 的提示词约束，结果 AI 只验了 🟢、
且在 🟡→🟢 升级后没补验活，用户随手点开报告里一条岗位就是「职位已下架」。
**提示词层的约束会被偷懒绕过，代码层的闸门不会。**

本脚本把「这条链接还活着吗」变成可复现的机械检查：
URL 形态 → HTTP 状态码 → 重定向落点 → 页面失效文案，四步判定，产出四态结论。

四态判定（与 SKILL.md 质检章节严格一致）
----------------------------------------
  alive      页面正常展示该具体岗位的 JD                  → 保留
  dead       明确失效文案 / 404 / 跳兜底页                → --apply 时移除
  not_detail 能打开但是列表页/公司主页/第三方资讯页        → --apply 时降级为 yellow
  unknown    抓不到（超时/登录墙/安全验证/JS 渲染）        → 保留原级别，标注人工核对

**铁律：抓不到内容一律 unknown，绝不判 dead。** BOSS/猎聘的安全验证墙极常见，
误删会丢掉真实好岗。宁可让用户多点一次，不可替用户丢掉机会。

用法
----
  python verify_links.py                    # 验活并打印报告（不改数据，安全预览）
  python verify_links.py --apply            # 验活并写回：移除 dead、降级 not_detail、加标注
  python verify_links.py --lint             # 只做 URL 形态静态体检，不发网络请求（秒出）
  python verify_links.py --check            # 只检查「是否已验活」，供 run.py 门禁调用
  python verify_links.py --in a.json --out b.json --workers 6 --timeout 15

字段契约（写回 jobs_raw.json 的每一条）
--------------------------------------
  verify_status    alive / dead / not_detail / unknown
  verify_evidence  判定依据（命中的文案 / 状态码 / URL 形态）
  verified_at      验活时间 ISO8601，run.py 用它判断验活是否过期

被移除的 dead 岗位不会凭空消失，会落到 dropped_dead.json 供追溯复核。
"""
import argparse
import gzip
import io
import json
import os
import re
import ssl
import sys
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Windows 控制台默认 GBK，中文/emoji 会炸，统一切 UTF-8
for _s in ("stdout", "stderr"):
    _f = getattr(sys, _s, None)
    if _f is not None and hasattr(_f, "reconfigure"):
        try:
            _f.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

DATA_HOME = os.environ.get("JOBRADAR_HOME") or os.path.expanduser("~/.job-radar")
DEFAULT_IN = os.path.join(DATA_HOME, "jobs_raw.json")
DROPPED = os.path.join(DATA_HOME, "dropped_dead.json")
VERIFY_REPORT = os.path.join(DATA_HOME, "verify_report.json")
UNKNOWN_OUT = os.path.join(DATA_HOME, "verify_unknown.json")
L2_PROMPT_OUT = os.path.join(DATA_HOME, "verify_l2_prompt.md")

# L2 统一指令模板。
# 教训：岗位多时要拆多个并行 subagent 分片验活，若每次由主 agent 现编指令，
# 分片之间的判定标准会漂移 —— 实测出现过「同样是投递截止日期已过，
# A 片判 unsure、B 片判 dead」。所以标准指令必须由脚本固化下发，不许各写各的。
L2_PROMPT_TMPL = """# L2 语义验活指令（分片时每个 subagent 都必须原样带上本段）

你是岗位链接验活质检员。脚本层（L1）已判过一轮，判不了的（反爬/登录墙/JS 渲染）
交给你：用 WebFetch 真实打开页面，**依据页面实际内容**判定岗位是否仍可投递。

## 判定三态（证据优先，严禁脑补）

- `alive`：页面确实展示了**这个岗位**的招聘信息（岗位名/JD/职责/要求等实质内容），
  且无失效提示、投递窗口未过。证据写清实际看到的岗位名、公司、薪资或 JD 片段。
- `dead`：满足任一条即可，证据必须引用页面原文：
  1. 出现失效文案（职位已下架 / 已停止招聘 / 职位不存在 / 当前职位审核中或已下线 / 招聘已结束）；
  2. 跳转到 404 或「页面不存在」；
  3. **页面写明的投递截止日期 / 网申结束日期早于今天（{today}）** —— 窗口关了就是投不了，
     即使页面没有任何下架字样也判 dead，证据写「投递已截止 YYYY-MM-DD」。
- `unsure`：抓不到、超时、跳登录/注册页、安全验证或验证码、返回加密乱码/反爬页、
  页面是列表或搜索页而非该岗位详情、内容为空、或打开后是**另一个岗位**（链接串了）。

## 铁律（违反会造成真实损失）

1. **抓不到内容一律 `unsure`，绝不允许因「抓不到」就判 `dead`。** 误删会让求职者丢掉真实好岗。
2. **不许推测**：没亲眼看到失效文案/过期日期就不能判 dead；没亲眼看到岗位内容就不能判 alive。
3. 聚合站与高校就业网（应届生网、全职网、各校就业信息网）**页面能打开 ≠ 还在招**，
   必须专门核对投递截止日期。
4. 链接域名与公司对不上时（例如第三方转载站），要核对页面里的公司/岗位是否确为目标岗位，
   对不上判 `unsure` 并说明。

## WebFetch 提问模板（逐条照用）

> 这个页面是否是一个仍在招聘的岗位详情页？请回答：1) 岗位名称 2) 公司名称
> 3) 薪资/JD 要点 4) 是否出现职位已下架/已停止招聘/不存在等失效提示
> 5) 是否写了投递截止日期或网申时间，具体是哪天 6) 是否是登录墙、验证码、
> 反爬加密页或列表页。只依据页面实际内容回答，不要推测。

若 WebFetch 提示重定向到其他 host，用新 URL 重试一次。

## 回填方式（不照做会导致回写失败）

直接在 `{unknown_file}` 上**原地补齐**每条的 `l2_status` 与 `l2_evidence` 两个字段，
**保留原有的 `idx` 和 `link` 字段不要改动、不要重排顺序、不要删条目**。
（脚本按 link 优先、idx 兜底来匹配；两个都丢就回写不上。）

填完运行：`python scripts/verify_links.py --import-l2`
"""
# AI 完成 L2 语义验活后，把裁决结果填回这个文件，再用 --import-l2 回写主数据
L2_IN = os.path.join(DATA_HOME, "verify_l2.json")
L2_VALID = ("alive", "dead", "unsure")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 人类可读标注的哨兵前缀，重跑时先剥离再追加 → 保证幂等，不会叠成一坨
NOTE_MARK = "【验活】"
NOTE_RE = re.compile(r"\s*【验活】[^【]*$")

# ---------------------------------------------------------------------------
# 判定规则表
# ---------------------------------------------------------------------------

# 明确失效文案 → dead。命中即判死，无需再看别的
DEAD_PATTERNS = [
    # 51job / 前程无忧（实测过期率最高的平台）
    "当前职位审核中或已下线", "该职位已经暂停招聘", "你选择的职位目前已经暂停招聘",
    # 实习僧（坑：JD 快照仍完整可见，只在顶部标一行下线）
    "当前职位已下线", "该职位已下线", "职位已下线",
    # 智联招聘
    "该职位已结束招聘", "职位已结束招聘", "该职位已暂停",
    # BOSS 直聘
    "职位已关闭", "该职位已停止招聘", "职位已停止招聘",
    # 猎聘 / 拉勾
    "该职位已暂停招聘", "职位已过期", "该职位已失效",
    # 通用中文
    "职位已下架", "该职位不存在", "职位不存在", "招聘已结束", "已停止招聘",
    "该岗位已招满", "报名已截止", "职位已失效", "该职位已被删除",
    "页面不存在", "您访问的页面不存在", "你访问的页面不存在", "抱歉，页面走丢了",
    # 英文
    "no longer available", "position has been closed", "job has expired",
    "this job is closed", "no longer accepting applications", "page not found",
]

# 登录墙 / 人机验证 → unknown（绝不判 dead）
WALL_PATTERNS = [
    "请先登录", "登录后查看", "请登录后", "立即登录查看",
    "安全验证", "请完成安全验证", "滑动验证", "人机验证", "拖动滑块",
    "访问过于频繁", "您的访问出现异常", "请输入验证码", "验证码错误",
    "captcha", "access denied", "403 forbidden", "just a moment",
    "请开启javascript", "please enable javascript",
    # WAF / 反爬挑战：页面正文被加密或替换成挑战脚本，拿到的不是真内容
    "_waf_", "__jsl_clearance", "acw_sc__v2", "security_verify",
    "checking your browser", "nocaptcha", "_ac_", "x5_tt",
]

# 真实岗位详情页应当出现的特征词。一个页面既无失效文案、又无任何岗位特征，
# 说明我们根本没拿到真实内容（WAF/JS 渲染），此时必须判 unknown 而非 alive。
# ⚠️ 这是本脚本最重要的一道防线：51job 的 WAF 加密页就是靠它兜住的。
JD_HINTS = [
    "岗位职责", "职位描述", "职位信息", "任职要求", "岗位要求", "工作职责",
    "职责描述", "任职资格", "岗位描述", "工作内容", "职位要求", "招聘人数",
    "工作地点", "立即投递", "申请职位", "投递简历", "我要应聘", "在线申请",
    "学历要求", "经验要求", "薪资待遇", "月薪", "实习", "校招", "招聘",
    "job description", "responsibilities", "qualifications", "apply now",
    "requirements", "we are looking for",
]

# 第三方资讯 / 工商查询站 → not_detail（这类页面永远不是岗位详情）
THIRD_PARTY_HOSTS = [
    "maimai.cn", "aiqicha.baidu.com", "qcc.com", "qichacha.com", "tianyancha.com",
    "zhihu.com", "csdn.net", "jianshu.com", "cnblogs.com", "juejin.cn",
    "mp.weixin.qq.com", "baijiahao.baidu.com", "sohu.com", "163.com",
    "sina.com.cn", "toutiao.com", "xiaohongshu.com/explore", "douban.com/group",
    "bilibili.com", "weibo.com",
]

# 已知招聘平台域名：这些站的岗位详情页几乎必带数字/哈希 ID，
# 若 path 里找不到 ID → 高置信度判为列表页
KNOWN_JOB_BOARDS = [
    "zhipin.com", "liepin.com", "zhaopin.com", "51job.com", "lagou.com",
    "shixiseng.com", "ciweishixi.com", "shixi.com", "rc114.com", "haitou.cc",
    "yingjiesheng.com", "nowcoder.com", "niuqizp.com", "jianxun.com",
    "dajie.com", "job592.com", "gaoxiaojob.com", "chinahr.com",
]

# 明确的列表 / 搜索 / 公司页路径特征 → not_detail
LIST_PATH_RE = re.compile(
    r"(^/?$)"                       # 站点主页
    r"|(/search)|(/sou)|(/so/)"     # 搜索页
    r"|(/list)|(/joblist)|(/zhaopin/?$)"
    r"|(/company/)|(/gongsi/)|(/firm/)|(/companies/)"
    r"|(/campus/?$)|(/careers/?$)|(/jobs/?$)|(/positions/?$)|(/job/?$)",
    re.I,
)
LIST_QUERY_RE = re.compile(r"[?&](keyword|query|kw|q|searchkey|jobArea|city)=", re.I)

# 岗位详情页的 ID 特征。命中即认为是「具体岗位页」，直接放行交给 HTTP 层判定。
# 这条规则宁松勿紧：误判成列表页会白白降级掉真实好岗（实测踩过坑）。
DETAIL_ID_RE = re.compile(
    r"(\d{5,})"                                  # 纯数字长 ID：170699160
    r"|(\d{2,}-\d{2,}-\d{2,})"                   # 分段数字：job-008-017-068.html
    r"|([A-Za-z]{2,}_[A-Za-z0-9]{6,})"           # 带前缀 slug：inn_xbre3s14mpci
    r"|([0-9a-fA-F]{16,})"                       # 长哈希
    r"|([A-Za-z0-9~_-]{20,})"                    # 超长 token：4280035b1f7ad2541XR72tS4FVI~
    # 字母数字混合的短 slug（牛企直聘 job-vyU5zCLNa.html 这类）
    r"|((?=[A-Za-z0-9-]*[A-Za-z])(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{6,}(?=\.html?(?:[?#]|$)))"
)

# 需登录平台：per-host 限速要更保守，避免触发风控
SLOW_HOSTS = ["zhipin.com", "liepin.com", "zhaopin.com", "51job.com", "lagou.com", "maimai.cn"]

_host_lock = threading.Lock()
_host_last = {}


def _host_of(url):
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _throttle(host):
    """per-host 最小访问间隔，礼貌抓取 + 规避风控。"""
    gap = 2.5 if any(h in host for h in SLOW_HOSTS) else 1.2
    while True:
        with _host_lock:
            now = time.time()
            last = _host_last.get(host, 0)
            if now - last >= gap:
                _host_last[host] = now
                return
            wait = gap - (now - last)
        time.sleep(min(wait, gap))


def _strip_html(raw):
    """粗暴提取正文文本：去 script/style/注释/标签，压缩空白。"""
    txt = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    txt = re.sub(r"(?s)<!--.*?-->", " ", txt)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = (txt.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", txt).strip()


def _decode(body, headers):
    enc = (headers.get("Content-Encoding") or "").lower()
    try:
        if "gzip" in enc:
            body = gzip.GzipFile(fileobj=io.BytesIO(body)).read()
        elif "deflate" in enc:
            body = zlib.decompress(body, -zlib.MAX_WBITS)
    except Exception:
        pass
    ctype = headers.get("Content-Type") or ""
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    charset = m.group(1) if m else None
    if not charset:
        head = body[:2048].decode("latin-1", "ignore")
        m2 = re.search(r'charset=["\']?([\w-]+)', head, re.I)
        charset = m2.group(1) if m2 else "utf-8"
    for cs in (charset, "utf-8", "gb18030", "latin-1"):
        try:
            return body.decode(cs, "strict")
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", "replace")


def url_shape_verdict(url):
    """静态 URL 形态判定，不发网络请求。返回 (verdict, evidence) 或 (None, None)。"""
    if not url or not url.strip():
        return "unknown", "无链接，无法验活"
    u = url.strip()
    if not u.lower().startswith(("http://", "https://")):
        return "not_detail", f"链接格式异常（非 http/https）：{u[:60]}"

    p = urlparse(u)
    host, path, query = p.netloc.lower(), p.path or "/", p.query or ""
    # 注意：不要无条件拼 "?"，否则会破坏正则里的行尾锚点（踩过坑）
    pq = path + ("?" + query if query else "")

    # 1) 第三方资讯 / 工商站：永远不是岗位详情页，无条件判定
    for h in THIRD_PARTY_HOSTS:
        if h in host + path:
            return "not_detail", f"第三方资讯/工商站（{h}），非岗位详情页"

    # 2) 站点主页
    if path in ("", "/") and not query:
        return "not_detail", "指向站点主页，无法确认具体岗位在招"

    # 3) 带岗位 ID → 判定为具体岗位页，放行给 HTTP 层
    #    顺序必须在列表规则之前：BOSS 的 /gongsi/job/<id>.html 是详情页而非公司页
    if DETAIL_ID_RE.search(pq):
        return None, None

    # 4) 无 ID 且命中搜索/列表/公司页形态
    if LIST_PATH_RE.search(path) or (query and LIST_QUERY_RE.search("?" + query)):
        return "not_detail", f"URL 形态为搜索/列表/公司页：{pq}"

    # 5) 已知招聘平台，但路径里找不到任何岗位 ID → 高置信度列表页
    if any(b in host for b in KNOWN_JOB_BOARDS):
        return "not_detail", f"招聘平台链接但路径无岗位 ID，疑似列表页：{path}"

    return None, None


def fetch_verdict(url, timeout=15, insecure_retry=True):
    """发起 HTTP 请求并判定。返回 (verdict, evidence)。"""
    host = _host_of(url)
    _throttle(host)

    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    })

    ctxs = [ssl.create_default_context()]
    if insecure_retry:
        lax = ssl.create_default_context()
        lax.check_hostname = False
        lax.verify_mode = ssl.CERT_NONE
        ctxs.append(lax)

    last_err = None
    for ctx in ctxs:
        try:
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                final_url = resp.geturl()
                code = resp.getcode()
                body = resp.read(600_000)
                text = _strip_html(_decode(body, resp.headers))
                return _judge(url, final_url, code, text)
        except HTTPError as e:
            code = e.code
            if code in (404, 410):
                return "dead", f"HTTP {code}，页面不存在"
            if code in (401, 403, 429):
                return "unknown", f"HTTP {code}（登录墙/风控拦截），需人工核对"
            if 500 <= code < 600:
                return "unknown", f"HTTP {code}（服务端错误），需人工核对"
            try:
                text = _strip_html(_decode(e.read(200_000), e.headers))
                v, ev = _judge(url, url, code, text)
                return v, ev
            except Exception:
                return "unknown", f"HTTP {code}，无法判定"
        except (URLError, ssl.SSLError, TimeoutError, OSError) as e:
            last_err = e
            continue
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue

    reason = str(last_err) if last_err else "未知错误"
    return "unknown", f"请求失败（{reason[:80]}），需人工核对"


def _judge(orig_url, final_url, code, text):
    """有了页面文本后的判定逻辑。顺序不可调换：dead > wall > 兜底页 > 内容量。"""
    low = text.lower()

    for pat in DEAD_PATTERNS:
        if pat.lower() in low:
            return "dead", f"页面命中失效文案「{pat}」"

    # 重定向落点：从详情页被踢回主页/搜索页 = 兜底页 = 岗位没了
    if final_url and final_url != orig_url:
        v, ev = url_shape_verdict(final_url)
        if v == "not_detail":
            op = urlparse(orig_url).path or "/"
            fp = urlparse(final_url).path or "/"
            if op != fp:
                return "dead", f"被重定向到兜底页（{fp}），原岗位页已不存在"

    for pat in WALL_PATTERNS:
        if pat.lower() in low:
            return "unknown", f"命中登录/验证墙或反爬挑战「{pat}」，需在已登录环境人工核对"

    if len(text) < 300:
        return "unknown", f"页面正文过短（{len(text)} 字符，疑似 JS 渲染），需人工核对"

    # 拿到内容了，但里面找不到任何岗位特征 → 说明拿到的不是真实 JD（WAF 加密页/空壳）
    hits = [h for h in JD_HINTS if h in low]
    if len(hits) < 2:
        return "unknown", (f"页面无岗位特征词（正文 {len(text)} 字符，疑似反爬加密或 JS 渲染），"
                           "脚本无法确认，需 AI/人工二次核对")

    return "alive", f"HTTP {code}，页面正常展示岗位内容（命中特征：{'、'.join(hits[:3])}）"


def verify_one(job, timeout=15, lint_only=False):
    url = (job.get("link") or "").strip()
    v, ev = url_shape_verdict(url)
    if v is not None:
        return v, ev
    if lint_only:
        return "skipped", "静态体检模式，未发起网络请求"
    return fetch_verdict(url, timeout=timeout)


# ---------------------------------------------------------------------------
# 标注（幂等）
# ---------------------------------------------------------------------------
NOTE_TEXT = {
    "alive": "✅ 已验活，页面正常在招",
    "dead": "❌ 已下架",
    "not_detail": "⚠️ 链接非具体岗位详情页，请到官网/平台搜索岗位名核实在招情况",
    "unknown": "⏳ 链接验活未确认，投递前请在已登录环境人工核对",
    "skipped": "",
}


def annotate(job, verdict):
    """把验活结论以固定哨兵段落写进 match_points，重跑先剥离旧标注保证幂等。"""
    base = NOTE_RE.sub("", job.get("match_points") or "").rstrip()
    note = NOTE_TEXT.get(verdict, "")
    job["match_points"] = f"{base} {NOTE_MARK}{note}".strip() if note else base
    return job


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def _export_unknown(jobs):
    """导出脚本判不了的条目，交给 AI 做第二层（语义）验活。

    双层验活分工：
      L1 脚本层 —— 快、确定、全量、零 token。能判死的直接判死。
      L2 AI 层  —— 只处理 L1 的 unknown，用 WebFetch 的渲染/语义能力补刀。
    强反爬平台（51job/BOSS/猎聘/智联）几乎必然落到 L2，别指望脚本能穿透 WAF。
    """
    unk = [{"idx": i, "company": j.get("company"), "title": j.get("title"),
            "link": j.get("link"), "source": j.get("source"),
            "why": j.get("verify_evidence"),
            # ↓ 待 AI 填写：alive=页面确为该岗位且在招 / dead=已下架或页面不存在 / unsure=确实打不开
            "l2_status": "", "l2_evidence": ""}
           for i, j in enumerate(jobs) if j.get("verify_status") == "unknown"
           and not j.get("l2_status")]
    if not unk:
        return 0
    os.makedirs(os.path.dirname(UNKNOWN_OUT) or ".", exist_ok=True)
    with open(UNKNOWN_OUT, "w", encoding="utf-8") as f:
        json.dump(unk, f, ensure_ascii=False, indent=2)
    # 同时落一份统一指令模板：分片并行验活时每个 subagent 都读它，
    # 避免各分片标准不一（曾出现同样「投递已截止」一片判 unsure、另一片判 dead）。
    with open(L2_PROMPT_OUT, "w", encoding="utf-8") as f:
        f.write(L2_PROMPT_TMPL.format(
            today=datetime.now().strftime("%Y-%m-%d"),
            unknown_file=UNKNOWN_OUT))
    print(f"待 AI 二次验活清单（{len(unk)} 条）：{UNKNOWN_OUT}")
    print(f"统一验活指令（分片必读，勿自行改写）：{L2_PROMPT_OUT}")
    print("   AI 逐条 WebFetch 打开后，在清单上原地补 l2_status（alive/dead/unsure）+ l2_evidence，")
    print("   保留 idx 与 link 字段不要动，然后运行：python scripts/verify_links.py --import-l2")
    return len(unk)


def cmd_import_l2(inp, l2_path, out=None):
    """回写 AI 的 L2 语义验活裁决，并清洗掉被判死的岗位。

    这一步是 L2 闭环的落地端：没有它，AI 的验活结论只停留在对话里，
    数据和报告依旧带着未确证的链接 —— 也就是死链继续漏网。
    """
    if not os.path.exists(l2_path):
        print(f"❌ 找不到 L2 裁决文件：{l2_path}")
        print("   请先运行 --export-unknown 导出清单，交 AI 填写 l2_status 后再回来。")
        return 1
    jobs = load_jobs(inp)
    with open(l2_path, encoding="utf-8") as f:
        verdicts = json.load(f)
    if isinstance(verdicts, dict):
        verdicts = verdicts.get("jobs") or verdicts.get("data") or []

    # 匹配策略：link 是唯一可靠主键，idx 仅在整份文件都没有 link 时兜底。
    #
    # 血泪教训（2026-08-02）：清单里的 idx 是「岗位在数据中的下标」，但人和 AI
    # 都会自然理解成「清单里的第几条」。两套编号一旦错位，裁决就会整体串岗 ——
    # 实测出现过「美团岗位挂着拼多多的验活证据」，还照此错删了 2 条好岗，
    # 而脚本全程毫无察觉。所以这里必须做交叉校验：公司/岗位名对不上就中止。
    by_link, by_idx, bad = {}, {}, []
    for v in verdicts:
        st = (v.get("l2_status") or "").strip().lower()
        if not st:
            continue
        payload = (st, (v.get("l2_evidence") or "").strip(),
                   (v.get("company") or "").strip(), (v.get("title") or "").strip())
        link = (v.get("link") or "").strip()
        if link:
            by_link[link] = payload
        idx = v.get("idx")
        if isinstance(idx, int) and 0 <= idx < len(jobs):
            by_idx[idx] = payload

    use_idx = not by_link          # 有 link 就绝不退回 idx，避免两套编号混用
    if by_link and by_idx:
        print("ℹ️ 裁决文件同时含 link 与 idx，一律以 link 为准（idx 语义易错位）。")
    if use_idx and by_idx:
        print("⚠️ 裁决文件没有 link 字段，改用 idx 匹配。")
        print("   注意 idx 必须是 --export-unknown 清单中每条自带的 idx 值，")
        print("   不是「清单里的第几条」——两者不同，错用会导致裁决整体串岗。")

    applied, now_iso, mismatch = 0, datetime.now().replace(microsecond=0).isoformat(), []
    for i, job in enumerate(jobs):
        link = (job.get("link") or "").strip()
        hit = by_link.get(link) or (by_idx.get(i) if use_idx else None)
        if not hit:
            continue
        st, ev, v_co, v_ti = hit
        if st not in L2_VALID:
            bad.append((link, st))
            continue
        # 交叉校验：裁决若带了公司/岗位名，必须与目标岗位对得上，否则说明编号错位
        j_co, j_ti = (job.get("company") or "").strip(), (job.get("title") or "").strip()
        if (v_co and j_co and v_co != j_co) or (v_ti and j_ti and v_ti != j_ti):
            mismatch.append((i, f"{j_co}·{j_ti}", f"{v_co}·{v_ti}"))
            continue
        job["l2_status"] = st
        job["l2_evidence"] = ev
        job["l2_verified_at"] = now_iso
        # 语义裁决优先级高于脚本判定：AI 真看过页面
        if st == "alive":
            job["verify_status"] = "alive"
            job["verify_evidence"] = f"AI二次验活：{ev or '页面确认在招'}"
        elif st == "dead":
            job["verify_status"] = "dead"
            job["verify_evidence"] = f"AI二次验活：{ev or '页面确认已下架'}"
        else:  # unsure：保留 unknown，但记录已裁决，门禁放行且报告显式警示
            job["verify_evidence"] = f"AI二次验活仍无法确认：{ev or '页面无法访问'}"
        applied += 1

    if bad:
        print(f"⚠️ {len(bad)} 条 l2_status 取值非法（须为 alive/dead/unsure），已跳过：")
        for link, st in bad[:5]:
            print(f"   · {st!r} ← {link[:70]}")

    # 交叉校验失败 = 编号错位，裁决张冠李戴。绝不能带病写入：
    # 一旦写入，错误的 dead 会删掉真实好岗，错误的 alive 会放行死链。
    if mismatch:
        print(f"❌ {len(mismatch)} 条裁决与岗位对不上号，已中止（数据未改动）。")
        print("   这通常是 idx 编号错位造成的：清单里的 idx 是岗位在数据中的下标，")
        print("   不是「清单里的第几条」。请改用 link 匹配，或核对 idx 取值。\n")
        for i, real, claim in mismatch[:6]:
            print(f"   · 数据第 {i} 条是「{real}」，裁决却写着「{claim}」")
        if len(mismatch) > 6:
            print(f"   … 另有 {len(mismatch) - 6} 条")
        return 1

    # 一条都没匹配上 = 裁决文件格式不对。这里必须硬失败：
    # 若继续往下走会打印「✅ 已回写 0 条」并原样落盘，用户以为 L2 做完了，
    # 实际上死链一条没清 —— 静默失败正是死链漏网的温床。
    if applied == 0:
        print("❌ L2 裁决一条都没能匹配上岗位数据，已中止（数据未改动）。")
        print(f"   裁决文件：{l2_path}（{len(verdicts)} 条）")
        print(f"   岗位数据：{inp}（{len(jobs)} 条）")
        print("\n   裁决文件必须是 JSON 数组，每条至少含 l2_status，且带 link 或 idx 之一：")
        print('     [{"idx": 0, "link": "https://...", "l2_status": "alive", "l2_evidence": "页面展示…"}]')
        print("   · link 需与岗位数据中的 link 完全一致")
        print("   · idx 为 --export-unknown 导出清单里的下标，不要重排或改写")
        print("   最稳妥的做法：直接在 verify_unknown.json 上原地补 l2_status/l2_evidence 两个字段。")
        return 1

    if applied < len(verdicts):
        print(f"⚠️ 裁决文件 {len(verdicts)} 条，仅 {applied} 条匹配上岗位数据，"
              f"{len(verdicts) - applied} 条未生效（link/idx 对不上，请核对）。")

    kept, dropped = [], []
    for job in jobs:
        if job.get("verify_status") == "dead":
            dropped.append(job)
            continue
        annotate(job, job.get("verify_status"))
        kept.append(job)

    out = out or inp
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    if dropped:
        hist = []
        if os.path.exists(DROPPED):
            try:
                with open(DROPPED, encoding="utf-8") as f:
                    hist = json.load(f)
            except Exception:
                hist = []
        hist.extend(dropped)
        with open(DROPPED, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)

    still = sum(1 for j in kept if j.get("verify_status") == "unknown" and not j.get("l2_status"))
    print(f"✅ 已回写 {applied} 条 L2 裁决 → {out}")
    print(f"   移除 AI 确认下架 {len(dropped)} 条" + (f"（备份至 {DROPPED}）" if dropped else ""))
    print(f"   剩余 {len(kept)} 条；仍未经 L2 裁决的 unknown：{still} 条")
    if still:
        print("   ⚠️ 门禁仍会拦截，请对剩余条目继续 L2 验活。")
    return 0


def load_jobs(path):
    if not os.path.exists(path):
        print(f"❌ 找不到岗位数据文件：{path}")
        print("   请先把 AI 返回的岗位 JSON 保存到该路径，再运行本脚本。")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("jobs") or data.get("data") or []
    if not isinstance(data, list):
        print("❌ 数据格式错误：期望 JSON 数组（岗位列表）。")
        sys.exit(1)
    return data


def cmd_check(path, max_age_hours=24, allow_unknown=False):
    """门禁检查：数据是否已完成验活。供 run.py 调用。退出码 0=通过，2=未通过。

    两道关：
      ① L1 —— 每条都得跑过脚本验活，且结果没过期。
      ② L2 —— 脚本判不了的 unknown，必须由 AI 语义裁决过（有 l2_status）。
    第 ② 关是"微创医疗已下架"那类事故的最后一道防线：强反爬平台的死链
    脚本看不穿，只会落到 unknown；若 unknown 能无条件放行，等于没验。
    """
    jobs = load_jobs(path)
    withlink = [j for j in jobs if (j.get("link") or "").strip()]
    unverified = [j for j in jobs if not j.get("verify_status")]
    stale, bad_ts = [], []
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    for j in jobs:
        ts = j.get("verified_at")
        if not ts:
            continue
        try:
            if datetime.fromisoformat(ts.replace("Z", "")) < cutoff:
                stale.append(j)
        except Exception:
            bad_ts.append(j)

    print(f"岗位总数 {len(jobs)}（带链接 {len(withlink)}）")
    print(f"未验活 {len(unverified)} 条 / 验活超过 {max_age_hours} 小时 {len(stale)} 条")
    if unverified or stale or bad_ts:
        print("\n❌ 验活门禁未通过。报告里每一条链接用户都可能点开，未验活不得出报告。")
        print(f"   请先运行：python scripts/verify_links.py --apply")
        for j in unverified[:5]:
            print(f"     · 未验活：{j.get('company', '')} {j.get('title', '')}")
        return 2
    dead_left = [j for j in jobs if j.get("verify_status") == "dead"]
    if dead_left:
        print(f"\n❌ 仍有 {len(dead_left)} 条已确认下架的岗位未清理，请运行 --apply。")
        return 2

    # 第 ② 关：unknown 必须经 AI 语义裁决
    pending = [j for j in jobs
               if j.get("verify_status") == "unknown" and not j.get("l2_status")]
    if pending:
        if allow_unknown:
            print(f"\n⚠️ 放行 {len(pending)} 条未经 L2 裁决的 unknown（--allow-unknown）。")
            print("   报告将打上『含未确证链接』水印，用户点开可能遇到已下架岗位。")
            os.environ["JOBRADAR_L2_PENDING"] = str(len(pending))
        else:
            print(f"\n❌ 有 {len(pending)} 条链接脚本判不了（反爬/登录墙/JS渲染），")
            print("   且尚未经 AI 第二层语义验活。这类链接正是『点开显示职位已下架』的高发区，")
            print("   不做 L2 就出报告 = 把风险直接甩给用户。")
            print(f"\n   请执行：")
            print(f"     1) python scripts/verify_links.py --export-unknown")
            print(f"     2) AI 逐条 WebFetch 打开，把 l2_status 填成 alive/dead/unsure")
            print(f"     3) python scripts/verify_links.py --import-l2")
            print(f"   （确要跳过请显式加 --allow-unknown，报告会打未确证水印）")
            for j in pending[:5]:
                print(f"     · 待L2：{j.get('company', '')} {j.get('title', '')}")
            if len(pending) > 5:
                print(f"     … 另有 {len(pending) - 5} 条")
            return 2

    n_unsure = sum(1 for j in jobs if j.get("l2_status") == "unsure")
    print("✅ 验活门禁通过。" + (f"（其中 {n_unsure} 条 AI 也无法确认，报告已标注警示）" if n_unsure else ""))
    return 0


def cmd_selftest():
    """内置回归自测：把踩过的坑固化成断言，改规则后跑一次即可确认没改坏。

    误判成本不对称：把真详情页误判为列表页 → 白白降级真实好岗；
    把列表页放行 → 顶多多一次 HTTP 请求。所以规则宁松勿紧。
    """
    detail = [  # 这些是真岗位详情页，必须放行（历史误伤case）
        "https://www.niuqizp.com/job-vyU5zCLNa.html",           # 牛企直聘 字母数字短slug
        "https://www.yingjiesheng.com/job-008-017-068.html",     # 应届生 分段数字ID
        "https://www.shixiseng.com/intern/inn_xbre3s14mpci",     # 实习僧 inn_前缀slug
        "https://www.zhipin.com/gongsi/job/c101280100/100000/4280035b1f7ad2541XR72tS4FVI~.html",  # BOSS 详情(含gongsi)
        "https://jobs.51job.com/shanghai/170699160.html",        # 51job 纯数字ID
        "https://jobs.zhaopin.com/CC000000000123456.htm",        # 智联 详情
        "https://careers.tencent.com/jobdesc.html?postId=1234567890",  # 腾讯 query带ID
    ]
    listing = [  # 这些是列表/主页/第三方页，必须判 not_detail
        "https://www.liepin.com/s/dsjaijgfxsginqndi/",
        "https://www.liepin.com/city-sh/zpaisfgcssxs9gf9/",
        "https://www.liepin.com/zpsfgcssxs/",
        "https://league.rc114.com/Union/Position",
        "https://www.deepseek.com/",
        "https://aiqicha.baidu.com/zhaopin/xxx",
        "https://maimai.cn/article/detail?fid=123",
        "https://we.51job.com/pc/search?keyword=%E7%AE%97%E6%B3%95",
    ]
    fails = []
    for u in detail:
        v, ev = url_shape_verdict(u)
        if v is not None:
            fails.append(f"[误伤真详情页] {u}\n    → 被判 {v}：{ev}")
    for u in listing:
        v, _ = url_shape_verdict(u)
        if v != "not_detail":
            fails.append(f"[漏判列表页] {u}\n    → 判定为 {v}")
    # 空链接
    if url_shape_verdict("")[0] != "unknown":
        fails.append("[空链接] 应判 unknown")
    # 失效文案命中
    if _judge("http://x/a", "http://x/a", 200,
              "岗位详情 " + "占位" * 200 + " 当前职位审核中或已下线")[0] != "dead":
        fails.append("[失效文案] 51job『当前职位审核中或已下线』应判 dead")
    # 登录墙不得判 dead
    if _judge("http://x/a", "http://x/a", 200,
              "请完成安全验证 " + "占位" * 200)[0] != "unknown":
        fails.append("[铁律] 安全验证墙必须判 unknown，绝不能判 dead")
    # 正常页面
    if _judge("http://x/a", "http://x/a", 200,
              "岗位职责 任职要求 " + "内容" * 300)[0] != "alive":
        fails.append("[正常页] 应判 alive")
    # WAF 加密页：本次事故的核心机制。拿到一大坨密文但无岗位特征，绝不能判 alive
    if _judge("http://x/a", "http://x/a", 200,
              '{"_waf_bd8ce2ce37":"EjKZL1EQa9k6"} ' + "3EJbNTQu9agLdTHqthe6n0K" * 400)[0] != "unknown":
        fails.append("[WAF密文] 51job 反爬加密页必须判 unknown，绝不能判 alive")
    # 空壳页：能打开、字数够，但没有任何岗位特征词
    if _judge("http://x/a", "http://x/a", 200, "欢迎光临 " * 300)[0] != "unknown":
        fails.append("[空壳页] 无岗位特征词应判 unknown")

    # --- L2 闭环断言：unknown 不做二层裁决绝不能放行 ---
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        raw = os.path.join(td, "jobs_raw.json")
        now = datetime.now().replace(microsecond=0).isoformat()
        data = [
            {"company": "A", "title": "岗A", "link": "http://x/a", "level": "green",
             "verify_status": "alive", "verify_evidence": "ok", "verified_at": now},
            {"company": "B", "title": "岗B", "link": "http://x/b", "level": "green",
             "verify_status": "unknown", "verify_evidence": "WAF", "verified_at": now},
        ]
        with open(raw, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            rc_block = cmd_check(raw)                       # 未裁决 → 必须拦
            rc_allow = cmd_check(raw, allow_unknown=True)   # 显式放行 → 通过
        if rc_block != 2:
            fails.append("[L2门禁] 未经AI裁决的 unknown 必须拦截（应返回2）")
        if rc_allow != 0:
            fails.append("[L2逃生阀] --allow-unknown 应放行（应返回0）")

        # 导入 AI 裁决：dead 要被清掉，alive 要升级
        l2 = os.path.join(td, "verify_l2.json")
        with open(l2, "w", encoding="utf-8") as f:
            json.dump([{"link": "http://x/b", "l2_status": "dead",
                        "l2_evidence": "页面显示该职位已下架"}], f, ensure_ascii=False)
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_import_l2(raw, l2)
        with open(raw, encoding="utf-8") as f:
            after = json.load(f)
        if len(after) != 1 or after[0]["company"] != "A":
            fails.append("[L2回写] AI 判 dead 的岗位应被移除")
        with contextlib.redirect_stdout(io.StringIO()):
            if cmd_check(raw) != 0:
                fails.append("[L2闭环] 裁决完成后门禁应放行")

    # --- 回写匹配断言：AI 常只回 idx 而丢掉 link，必须能兜底匹配 ---
    with tempfile.TemporaryDirectory() as td:
        raw = os.path.join(td, "jobs_raw.json")
        now = datetime.now().replace(microsecond=0).isoformat()
        with open(raw, "w", encoding="utf-8") as f:
            json.dump([
                {"company": "A", "title": "岗A", "link": "http://x/a", "level": "green",
                 "verify_status": "unknown", "verify_evidence": "登录墙", "verified_at": now},
                {"company": "B", "title": "岗B", "link": "http://x/b", "level": "green",
                 "verify_status": "unknown", "verify_evidence": "登录墙", "verified_at": now},
            ], f, ensure_ascii=False)
        # 只给 idx，不给 link
        l2 = os.path.join(td, "l2.json")
        with open(l2, "w", encoding="utf-8") as f:
            json.dump([{"idx": 0, "l2_status": "alive", "l2_evidence": "页面在招"},
                       {"idx": 1, "l2_status": "dead", "l2_evidence": "职位已下架"}],
                      f, ensure_ascii=False)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cmd_import_l2(raw, l2)
        with open(raw, encoding="utf-8") as f:
            after = json.load(f)
        if rc != 0 or len(after) != 1 or after[0]["company"] != "A":
            fails.append("[L2回写] 仅含 idx（无 link）的裁决必须能匹配并生效")

        # 全都对不上时必须硬失败，且不得改动数据
        raw2 = os.path.join(td, "jobs_raw2.json")
        origin = [{"company": "C", "title": "岗C", "link": "http://x/c", "level": "green",
                   "verify_status": "unknown", "verify_evidence": "登录墙", "verified_at": now}]
        with open(raw2, "w", encoding="utf-8") as f:
            json.dump(origin, f, ensure_ascii=False)
        bad_l2 = os.path.join(td, "bad.json")
        with open(bad_l2, "w", encoding="utf-8") as f:
            json.dump([{"company": "C", "l2_status": "alive"}], f, ensure_ascii=False)
        with contextlib.redirect_stdout(io.StringIO()):
            rc_bad = cmd_import_l2(raw2, bad_l2)
        with open(raw2, encoding="utf-8") as f:
            untouched = json.load(f)
        if rc_bad == 0:
            fails.append("[L2静默失败] 零匹配必须返回非0，不能假装成功")
        if untouched != origin:
            fails.append("[L2静默失败] 零匹配时不得改动原数据")

        # 串岗事故复现（2026-08-02 真实踩坑）：idx 错位导致裁决张冠李戴，
        # 当时脚本照单全收还错删了 2 条好岗。必须靠交叉校验当场拦下。
        raw3 = os.path.join(td, "jobs_raw3.json")
        org3 = [{"company": "美团", "title": "Agent算法实习生", "link": "http://x/mt",
                 "level": "green", "verify_status": "unknown",
                 "verify_evidence": "登录墙", "verified_at": now}]
        with open(raw3, "w", encoding="utf-8") as f:
            json.dump(org3, f, ensure_ascii=False)
        cross = os.path.join(td, "cross.json")
        with open(cross, "w", encoding="utf-8") as f:  # idx 对上了，公司却是别家
            json.dump([{"idx": 0, "company": "商汤科技", "title": "算法实习生（多模态方向）",
                        "l2_status": "dead", "l2_evidence": "已下架"}], f, ensure_ascii=False)
        with contextlib.redirect_stdout(io.StringIO()):
            rc_cross = cmd_import_l2(raw3, cross)
        with open(raw3, encoding="utf-8") as f:
            kept3 = json.load(f)
        if rc_cross == 0:
            fails.append("[L2串岗] 公司/岗位对不上的裁决必须中止（应返回非0）")
        if kept3 != org3:
            fails.append("[L2串岗] 交叉校验失败时不得改动原数据")

    # --- 统一指令模板断言：分片标准漂移的根因 ---
    tmpl = L2_PROMPT_TMPL.format(today="2026-01-01", unknown_file="x.json")
    for kw in ("投递截止日期", "抓不到内容一律", "idx", "link"):
        if kw not in tmpl:
            fails.append(f"[L2模板] 统一指令必须包含关键规则：{kw}")

    n = len(detail) + len(listing) + 6 + 4 + 4 + 4 + 2
    if fails:
        print(f"❌ 自测未通过（{len(fails)}/{n} 项失败）：\n")
        for f in fails:
            print("  " + f)
        return 1
    print(f"✅ 自测全部通过（{n} 项）：详情页零误伤、列表页全识别、失效文案命中、登录墙不误杀。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="岗位链接验活器（纯标准库）")
    ap.add_argument("--in", dest="inp", default=DEFAULT_IN, help="输入 jobs_raw.json")
    ap.add_argument("--out", dest="out", default=None, help="输出路径（默认原地写回）")
    ap.add_argument("--apply", action="store_true", help="写回结果：移除 dead、降级 not_detail、加标注")
    ap.add_argument("--lint", action="store_true", help="只做 URL 形态静态体检，不发网络请求")
    ap.add_argument("--check", action="store_true", help="只检查是否已验活（供流水线门禁）")
    ap.add_argument("--selftest", action="store_true", help="跑内置回归自测（改判定规则后必跑）")
    ap.add_argument("--export-unknown", action="store_true",
                    help="导出脚本判不了的条目清单，交 AI 做第二层语义验活")
    ap.add_argument("--import-l2", action="store_true",
                    help="回写 AI 的 L2 裁决（读 verify_l2.json），并清掉被判死的岗位")
    ap.add_argument("--l2-file", default=L2_IN, help=f"L2 裁决文件路径（默认 {L2_IN}）")
    ap.add_argument("--allow-unknown", action="store_true",
                    help="放行未经 L2 裁决的 unknown（报告会打未确证水印，慎用）")
    ap.add_argument("--max-age-hours", type=int, default=24, help="验活结果有效期（小时）")
    ap.add_argument("--workers", type=int, default=6, help="并发线程数")
    ap.add_argument("--timeout", type=int, default=15, help="单条请求超时（秒）")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(cmd_selftest())
    if args.check:
        sys.exit(cmd_check(args.inp, args.max_age_hours, args.allow_unknown))
    if args.import_l2:
        sys.exit(cmd_import_l2(args.inp, args.l2_file, args.out))
    if args.export_unknown:
        jobs = load_jobs(args.inp)
        n = _export_unknown(jobs)
        if not n:
            print("✅ 没有待 L2 裁决的条目（unknown 均已裁决或不存在）。")
        sys.exit(0)

    jobs = load_jobs(args.inp)
    total = len(jobs)
    mode = "静态体检（不联网）" if args.lint else f"联网验活（并发 {args.workers}，超时 {args.timeout}s）"
    print(f"🔍 开始{mode}：共 {total} 条岗位\n")

    results = [None] * total
    done = [0]
    lock = threading.Lock()

    def work(i):
        job = jobs[i]
        v, ev = verify_one(job, timeout=args.timeout, lint_only=args.lint)
        results[i] = (v, ev)
        with lock:
            done[0] += 1
            icon = {"alive": "✅", "dead": "❌", "not_detail": "⚠️", "unknown": "⏳"}.get(v, "·")
            print(f"  [{done[0]:>3}/{total}] {icon} {v:<10} {(job.get('company') or '')[:14]:<14} "
                  f"{(job.get('title') or '')[:26]}")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        list(ex.map(work, range(total)))

    now_iso = datetime.now().replace(microsecond=0).isoformat()
    counts = {"alive": 0, "dead": 0, "not_detail": 0, "unknown": 0, "skipped": 0}
    dead_list, nd_list, unk_list = [], [], []

    for i, job in enumerate(jobs):
        v, ev = results[i] or ("unknown", "未执行")
        counts[v] = counts.get(v, 0) + 1
        job["verify_status"] = v
        job["verify_evidence"] = ev
        job["verified_at"] = now_iso
        label = f"{job.get('company', '')} · {job.get('title', '')} [{job.get('source', '')}]"
        if v == "dead":
            dead_list.append((label, ev))
        elif v == "not_detail":
            nd_list.append((label, ev))
        elif v == "unknown":
            unk_list.append((label, ev))

    print("\n" + "=" * 68)
    print(f"验活结果：✅ alive {counts['alive']} / ❌ dead {counts['dead']} / "
          f"⚠️ not_detail {counts['not_detail']} / ⏳ unknown {counts['unknown']}")
    print("=" * 68)
    for name, lst in (("❌ 已下架（--apply 将移除）", dead_list),
                      ("⚠️ 非岗位详情页（--apply 将降级为🟡）", nd_list)):
        if lst:
            print(f"\n{name}：")
            for label, ev in lst:
                print(f"   · {label}\n     └ {ev}")
    if unk_list:
        print(f"\n⏳ 验活未确认 {len(unk_list)} 条（保留原级别，已标注人工核对）：")
        for label, _ in unk_list[:10]:
            print(f"   · {label}")
        if len(unk_list) > 10:
            print(f"   … 另有 {len(unk_list) - 10} 条")

    if counts.get("unknown"):
        print(f"\n💡 下一步：{counts['unknown']} 条脚本判不了（反爬/登录墙/JS 渲染）。")
        print("   强反爬平台（51job/BOSS/猎聘/智联）的死链只有 AI 的 WebFetch 能看穿，")
        print("   请把下面这份清单交给 AI 做第二层语义验活：")
        print(f"   python scripts/verify_links.py --export-unknown  →  {UNKNOWN_OUT}")

    if not args.apply:
        print("\n（预览模式，未改动数据。确认无误后加 --apply 执行清洗）")
        os.makedirs(os.path.dirname(VERIFY_REPORT) or ".", exist_ok=True)
        with open(VERIFY_REPORT, "w", encoding="utf-8") as f:
            json.dump([{"company": j.get("company"), "title": j.get("title"),
                        "link": j.get("link"), "verify_status": j.get("verify_status"),
                        "verify_evidence": j.get("verify_evidence")} for j in jobs],
                      f, ensure_ascii=False, indent=2)
        print(f"明细已写入：{VERIFY_REPORT}")
        _export_unknown(jobs)
        return

    # --apply：执行清洗
    kept, dropped = [], []
    for job in jobs:
        v = job.get("verify_status")
        if v == "dead":
            dropped.append(job)
            continue
        if v == "not_detail" and (job.get("level") or "").lower() == "green":
            job["level"] = "yellow"
        annotate(job, v)
        kept.append(job)

    out = args.out or args.inp
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    if dropped:
        hist = []
        if os.path.exists(DROPPED):
            try:
                with open(DROPPED, encoding="utf-8") as f:
                    hist = json.load(f)
            except Exception:
                hist = []
        hist.extend(dropped)
        with open(DROPPED, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)

    lv = {"green": 0, "yellow": 0, "red": 0}
    for j in kept:
        lv[(j.get("level") or "yellow").lower()] = lv.get((j.get("level") or "yellow").lower(), 0) + 1
    print(f"\n✅ 已写回 {out}")
    print(f"   移除已下架 {len(dropped)} 条（备份至 {DROPPED}）")
    print(f"   剩余 {len(kept)} 条：🟢 {lv['green']} / 🟡 {lv['yellow']} / 🔴 {lv['red']}")
    _export_unknown(kept)


if __name__ == "__main__":
    main()
