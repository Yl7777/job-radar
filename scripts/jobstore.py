#!/usr/bin/env python3
"""岗位增量库 — 让检索结果只包含"真正发生变化"的岗位。

设计原则（来自用户反馈）：
  - 宁多勿少、全面、真实、幻觉低、匹配度高。
  - 同一家公司完全可能有多个"同名不同岗"的职位，因此**绝对不能**只靠
    (公司 + 岗位名 + 城市) 来判定重复——那会把真实的不同岗位误合并。
  - 可靠的唯一标识是岗位链接（URL）。同一个招聘帖子无论被哪家聚合站转载，
    只要原文 URL 一致就是同一个岗位。
  - 链接缺失时，退而用"岗位描述文本的归一化哈希"判断，但**必须同时命中
    同公司 + 同标题**才判重，避免不同帖子被误并。
  - 既没有 URL 又没有描述的纯快照 → 一律视为新岗位（宁可重复也不漏）。

相对"每次全量输出"，本模块额外识别四种**变化事件**（借鉴增量追踪思想，
但保持轻量、纯标准库）：
  - new              ：从没见过的新链接
  - updated          ：同一条链接，JD / 薪资 / 要求等核心内容变了（content_hash 变化）
  - reopened         ：之前疑似下架（closed），本次又重新出现
  - possibly_closed  ：连续 N 次（默认 3）在"本批覆盖范围内"都搜不到 → 疑似下架（一次没搜到不误判，且仅针对本批实际检索的城市×平台，避免局部检索误判）

参考 CareerForge job-hunt 的"每次全量输出"思路，本 skill 由作者独立实现了增量式去重：AI 负责搜，
本模块负责"只推变化"。

用法：
  python jobstore.py init
  python jobstore.py filter  < jobs.json > new_jobs.json   # 过滤出变化并入库
  python jobstore.py filter --dry-run < jobs.json          # 只看变化，不写库
  python jobstore.py filter --missing-threshold 3 < jobs.json
  python jobstore.py mark --url <岗位链接> --status applied
  python jobstore.py apply --url <岗位链接> --status 已投递 --note "8/1投递"
  python jobstore.py applications            # 列出全部投递进度
  python jobstore.py app-stats               # 投递进度统计
  python jobstore.py stats
  python jobstore.py recent --days 7

输入 JSON（数组，字段尽量对齐 skill 的 14 列导出规范；link / description 越全去重越准）：
  [{"title":"AI产品运营实习生","company":"字节跳动","city":"上海",
    "salary":"200-300/天","exp":"在校","posted":"3天前","level":"green",
    "match_points":"","tags":"","source":"牛客","link":"https://...",
    "description":"负责...","company_tag":"AI独角兽"}]
输出 JSON（new_jobs.json）每条带 "_event" 字段：new / updated / reopened / possibly_closed。
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta

# 用户数据外移到 skill 之外（可用 JOBRADAR_HOME 覆盖），避免重装/分享时误删
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


DATA_HOME = resolve_data_home()
DB_PATH = os.path.join(DATA_HOME, "data", "jobs.db")

# 连续多少次"完整检索却搜不到"才判定疑似下架，避免一次搜不到就误报
DEFAULT_MISSING_THRESHOLD = 3

# 公司名归一化时剥离的后缀：避免"北京字节跳动科技有限公司"和"字节跳动"被当成两家
COMPANY_NOISE = [
    "股份有限公司", "有限责任公司", "科技有限公司", "网络科技有限公司",
    "信息technology", "有限公司", "集团", "分公司", "总公司", "公司",
    "co.,ltd", "co.ltd", "coltd", "ltd", "inc", "corp", "corporation", "limited",
]
TITLE_NOISE_PAT = re.compile(
    r"(急招|急聘|高薪|包住|双休|五险一金|可远程|base\s*\w+|[jJ]\d+|"
    r"\d+[kK]-\d+[kK]|应届|校招|社招|实习生?)"
)
# 归一化 URL 时剥离的跟踪参数（只去掉来源/追踪类，保留真实查询参数如岗位 id）
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "from", "spm", "trace", "tracelog", "tracelogid", "track", "tracking",
    "ref", "refer", "referrer", "share", "shareid", "clickid", "clk",
    "_t", "t", "timestamp", "ts", "_", "v", "ver", "version", "cache",
    "scene", "channel", "position", "index", "clicktime", "b_from",
    "campaign_id", "cmpid", "kwd", "iknow", "pcm", "trk",
}


# --------------------------------------------------------------------------- #
# 归一化                                                                       #
# --------------------------------------------------------------------------- #
def norm_url(u):
    """把岗位链接归一化成可比较的形式。

    策略（比"整段丢弃 query"更规范）：
      - 去掉协议、www. 前缀、fragment。
      - 仅剥离已知的跟踪参数（utm_* / from / spm / trace / ref / t / pcm ...），
        保留有意义的查询参数（如某些平台的岗位 id 就在 query 里）。
      - 去掉末尾斜杠。
    例如：
      https://www.zhipin.com/job_detail/x.html?from=search&utm_source=x
        -> zhipin.com/job_detail/x.html
    """
    if not u:
        return ""
    u = u.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0]
    if "?" in u:
        path, qs = u.split("?", 1)
        kept = []
        for kv in qs.split("&"):
            if not kv:
                continue
            k = kv.split("=", 1)[0]
            if k in TRACKING_PARAMS or k.startswith("utm_"):
                continue
            kept.append(kv)
        u = path + ("?" + "&".join(kept) if kept else "")
    return u.rstrip("/")


def norm_desc(d):
    """岗位描述归一化：去空白、去标点，只留字母数字与中文，用于哈希比对。"""
    if not d:
        return ""
    d = d.lower()
    d = re.sub(r"\s+", "", d)
    d = re.sub(r"[^\w\u4e00-\u9fff]", "", d)
    return d


def desc_key(d):
    """描述文本足够长才算数（太短无法区分），否则返回空串（不参与判重）。"""
    nd = norm_desc(d)
    return hashlib.sha1(nd.encode("utf-8")).hexdigest()[:16] if len(nd) >= 40 else ""


def content_hash_of(job):
    """岗位核心内容的哈希，用于检测 JD / 薪资 / 要求等是否发生变化。"""
    parts = [
        job.get("title", ""), job.get("company", ""), job.get("city", ""),
        job.get("salary", ""), job.get("description", ""), job.get("tags", ""),
        job.get("match_points", ""),
    ]
    s = norm_desc(" ".join(parts))
    # 内容太短无法可靠判变，返回空串（视为未变化）
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16] if len(s) >= 20 else ""


def _strip(text, noise_list):
    t = (text or "").strip().lower()
    for n in noise_list:
        t = t.replace(n.lower(), "")
    return t


def norm_company(text):
    c = _strip(text, COMPANY_NOISE)
    return re.sub(r"[^\w\u4e00-\u9fff]", "", c)


def norm_title(text):
    t = TITLE_NOISE_PAT.sub("", (text or "").lower())
    t = re.sub(r"[（(\[【].*?[）)\]】]", "", t)
    return re.sub(r"[^\w\u4e00-\u9fff]", "", t)


def url_key_of(job):
    return norm_url(job.get("link"))


def desc_key_of(job):
    return desc_key(job.get("description", ""))


# --------------------------------------------------------------------------- #
# 数据库                                                                       #
# --------------------------------------------------------------------------- #
def connect():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _add_column(conn, table, col, definition):
    """安全加列：已存在则忽略（兼容旧库）。"""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
    except sqlite3.OperationalError:
        pass


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            url_key      TEXT PRIMARY KEY,
            desc_key     TEXT,
            norm_company TEXT,
            norm_title   TEXT,
            title        TEXT,
            company      TEXT,
            city         TEXT,
            salary       TEXT,
            exp          TEXT,
            posted       TEXT,
            level        TEXT,
            match_points TEXT,
            tags         TEXT,
            source       TEXT,
            link         TEXT,
            description  TEXT,
            job_type     TEXT,
            status       TEXT DEFAULT 'new',
            first_seen   TEXT,
            last_seen    TEXT,
            seen_count   INTEGER DEFAULT 1,
            content_hash TEXT,
            missing_count INTEGER DEFAULT 0,
            closed       INTEGER DEFAULT 0,
            last_event   TEXT,
            company_tag  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_desc     ON jobs(desc_key);
        CREATE INDEX IF NOT EXISTS idx_company  ON jobs(norm_company);
        CREATE INDEX IF NOT EXISTS idx_status   ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_first    ON jobs(first_seen);

        CREATE TABLE IF NOT EXISTS runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ran_at          TEXT,
            mode            TEXT,
            fetched         INTEGER,
            new_count       INTEGER,
            dup_count       INTEGER,
            updated_count   INTEGER,
            reopened_count  INTEGER,
            closed_count    INTEGER,
            covered_cities  TEXT,
            covered_sources TEXT
        );

        CREATE TABLE IF NOT EXISTS applications (
            url_key    TEXT PRIMARY KEY,
            company    TEXT,
            title      TEXT,
            city       TEXT,
            status     TEXT DEFAULT 'todo',
            applied_at TEXT,
            note       TEXT,
            updated_at TEXT
        );
        """
    )
    # 兼容旧库：补齐增量追踪相关列（首次运行在已存在的库上也不会报错）
    for col, ddl in [
        ("content_hash", "TEXT"),
        ("missing_count", "INTEGER DEFAULT 0"),
        ("closed", "INTEGER DEFAULT 0"),
        ("last_event", "TEXT"),
        ("company_tag", "TEXT"),
        ("updated_count", "INTEGER"),
        ("reopened_count", "INTEGER"),
        ("closed_count", "INTEGER"),
        ("covered_cities", "TEXT"),
        ("covered_sources", "TEXT"),
    ]:
        _add_column(conn, "jobs" if col in (
            "content_hash", "missing_count", "closed", "last_event", "company_tag"
        ) else "runs", col, ddl)
    # 旧库补齐索引（列可能刚加上，用 try/except 兜底）
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_closed ON jobs(closed)")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def find_desc_dup(conn, job):
    """链接缺失时，用描述哈希判重——但必须同公司 + 同标题，避免误并。"""
    dk = desc_key_of(job)
    if not dk:
        return None
    nc, nt = norm_company(job.get("company", "")), norm_title(job.get("title", ""))
    if not nc or not nt:
        return None
    row = conn.execute(
        "SELECT url_key FROM jobs WHERE desc_key = ? AND norm_company = ? AND norm_title = ?",
        (dk, nc, nt),
    ).fetchone()
    return row["url_key"] if row else None


# --------------------------------------------------------------------------- #
# 命令实现                                                                     #
# --------------------------------------------------------------------------- #
def cmd_filter(args):
    conn = connect()
    init_db(conn)

    raw = sys.stdin.read().strip()
    if not raw:
        print("[]")
        return
    jobs = json.loads(raw)
    if isinstance(jobs, dict):
        jobs = jobs.get("jobs", [])

    # 本批实际覆盖的城市 / 来源平台范围，供"缺失检测"判定，避免局部检索误判下架
    covered_cities = set(j.get("city") for j in jobs if j.get("city"))
    covered_sources = set(j.get("source") for j in jobs if j.get("source"))

    now = datetime.now().isoformat(timespec="seconds")
    threshold = args.missing_threshold
    new_jobs, dup_count = [], 0
    events = {"new": 0, "updated": 0, "reopened": 0, "possibly_closed": 0}

    # 本批次内去重用的集合
    batch_urls = set()
    batch_descs = set()

    for job in jobs:
        uk = url_key_of(job)
        dk = desc_key_of(job)
        ch = content_hash_of(job)

        # —— 本批次内部重复 —— #
        if uk and uk in batch_urls:
            dup_count += 1
            continue
        if dk and dk in batch_descs:
            dup_count += 1
            continue
        if uk:
            batch_urls.add(uk)
        if dk:
            batch_descs.add(dk)

        hit = None
        if uk:
            row = conn.execute(
                "SELECT * FROM jobs WHERE url_key = ?", (uk,)
            ).fetchone()
            if row:
                hit = row
        if hit is None:
            hit_key = find_desc_dup(conn, job)
            if hit_key:
                hit = conn.execute(
                    "SELECT * FROM jobs WHERE url_key = ?", (hit_key,)
                ).fetchone()

        if hit:
            dup_count += 1
            if args.dry_run:
                continue
            old_hash = hit["content_hash"] or ""
            was_closed = bool(hit["closed"])
            if was_closed:
                event = "reopened"
            elif ch and old_hash and ch != old_hash:
                event = "updated"
            else:
                event = "unchanged"
            conn.execute(
                """UPDATE jobs SET last_seen = ?, seen_count = seen_count + 1,
                       missing_count = 0, content_hash = ?, last_event = ?, closed = 0
                       WHERE url_key = ?""",
                (now, ch, event, hit["url_key"]),
            )
            if event in ("updated", "reopened"):
                job["_event"] = event
                job["_key"] = hit["url_key"]
                new_jobs.append(job)
                events[event] += 1
            continue

        # —— 真·新增 —— #
        key = uk or dk or f"unknown:{len(new_jobs)}"
        job["_key"] = key
        job["_event"] = "new"
        new_jobs.append(job)
        events["new"] += 1

        if not args.dry_run:
            nc, nt = norm_company(job.get("company", "")), norm_title(job.get("title", ""))
            conn.execute(
                """INSERT OR IGNORE INTO jobs
                   (url_key, desc_key, norm_company, norm_title, title, company, city,
                    salary, exp, posted, level, match_points, tags, source, link,
                    description, job_type, status, first_seen, last_seen, seen_count,
                    content_hash, missing_count, closed, last_event, company_tag)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?,?,1,?,0,0,'new',?)""",
                (key, dk, nc, nt, job.get("title"), job.get("company"), job.get("city"),
                 job.get("salary"), job.get("exp"), job.get("posted"), job.get("level"),
                 job.get("match_points"), job.get("tags"), job.get("source"),
                 job.get("link"), job.get("description"), job.get("job_type"),
                 now, now, ch, job.get("company_tag", "")),
            )

    # —— 缺失检测：本批没搜到的"在招"岗位，missing_count+1；达阈值标疑似下架 —— #
    # 只对本批实际覆盖到的 (城市×平台) 范围判定缺失，避免只搜了部分平台却把
    # 其它平台的在招岗误判为"疑似下架"。
    if not args.dry_run and batch_urls:
        for r in conn.execute("SELECT * FROM jobs WHERE closed = 0"):
            if r["url_key"] in batch_urls:
                continue
            rc = (r["city"] or "").strip()
            rs = (r["source"] or "").strip()
            in_coverage = True
            if covered_cities and covered_sources and rc and rs:
                in_coverage = (rc in covered_cities) and (rs in covered_sources)
            if not in_coverage:
                continue
            mc = (r["missing_count"] or 0) + 1
            if mc >= threshold:
                conn.execute(
                    """UPDATE jobs SET missing_count = ?, closed = 1,
                       last_event = 'possibly_closed', last_seen = ? WHERE url_key = ?""",
                    (mc, now, r["url_key"]),
                )
                rec = dict(r)
                rec["_event"] = "possibly_closed"
                new_jobs.append(rec)
                events["possibly_closed"] += 1
            else:
                conn.execute(
                    "UPDATE jobs SET missing_count = ? WHERE url_key = ?", (mc, r["url_key"])
                )

    if not args.dry_run:
        conn.execute(
            """INSERT INTO runs (ran_at, mode, fetched, new_count, dup_count,
               updated_count, reopened_count, closed_count, covered_cities, covered_sources)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (now, "search", len(jobs), events["new"], dup_count,
             events["updated"], events["reopened"], events["possibly_closed"],
             json.dumps(sorted(covered_cities), ensure_ascii=False),
             json.dumps(sorted(covered_sources), ensure_ascii=False)),
        )
        conn.commit()

    sys.stderr.write(
        f"[jobstore] 抓取 {len(jobs)} 条 → 新增 {events['new']} / 更新 {events['updated']} / "
        f"重开 {events['reopened']} / 疑似下架 {events['possibly_closed']} / 重复 {dup_count}"
        f"{'（dry-run，未写库）' if args.dry_run else ''}\n"
    )
    print(json.dumps(new_jobs, ensure_ascii=False, indent=2))


def cmd_mark(args):
    conn = connect()
    init_db(conn)
    if args.url:
        key = norm_url(args.url)
        cur = conn.execute("UPDATE jobs SET status = ? WHERE url_key = ?", (args.status, key))
    elif args.company:
        cur = conn.execute(
            "UPDATE jobs SET status = ? WHERE norm_company LIKE ?",
            (args.status, f"%{norm_company(args.company)}%"),
        )
    else:
        sys.exit("需要 --url 或 --company")
    conn.commit()
    print(f"已把 {cur.rowcount} 条岗位标记为 {args.status}")


APPLY_STATES = ["todo", "筛选中", "已投递", "笔试", "面试中", "终面", "Offer", "拒信", "放弃"]


def cmd_apply(args):
    """记录 / 更新某岗位的投递进度（与"岗位是否在招"分表管理）。"""
    conn = connect()
    init_db(conn)
    uk = norm_url(args.url or args.link or "")
    if not uk:
        sys.exit("需要 --url 或 --link 指定岗位链接")
    now = datetime.now().isoformat(timespec="seconds")
    row = conn.execute(
        "SELECT company, title, city FROM jobs WHERE url_key = ?", (uk,)
    ).fetchone()
    company = args.company or (row["company"] if row else "")
    title = args.title or (row["title"] if row else "")
    city = args.city or (row["city"] if row else "")

    existing = conn.execute(
        "SELECT applied_at FROM applications WHERE url_key = ?", (uk,)
    ).fetchone()
    if existing:
        applied_at = args.applied_at or existing["applied_at"] or now
        conn.execute(
            """UPDATE applications SET status = ?, note = ?, updated_at = ?,
               company = ?, title = ?, city = ? WHERE url_key = ?""",
            (args.status, args.note or "", now, company, title, city, uk),
        )
    else:
        applied_at = args.applied_at or now
        conn.execute(
            """INSERT INTO applications (url_key, company, title, city, status,
               applied_at, note, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (uk, company, title, city, args.status, applied_at, args.note or "", now),
        )
    conn.commit()
    print(f"投递进度已更新：{company} · {title} → {args.status}"
          f"（首次投递 {applied_at[:10]}）")


def cmd_applications(args):
    conn = connect()
    init_db(conn)
    rows = conn.execute(
        "SELECT * FROM applications ORDER BY updated_at DESC"
    ).fetchall()
    print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))


def cmd_app_stats(args):
    conn = connect()
    init_db(conn)
    print("投递进度统计：")
    total = conn.execute("SELECT COUNT(*) c FROM applications").fetchone()["c"]
    print(f"  总记录：{total}")
    for row in conn.execute(
        "SELECT status, COUNT(*) c FROM applications GROUP BY status ORDER BY c DESC"
    ):
        print(f"  {row['status']}: {row['c']}")


def cmd_stats(args):
    conn = connect()
    init_db(conn)
    total = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    print(f"库内岗位总数：{total}（疑似下架 {conn.execute('SELECT COUNT(*) c FROM jobs WHERE closed=1').fetchone()['c']}）")
    for row in conn.execute("SELECT status, COUNT(*) c FROM jobs GROUP BY status"):
        print(f"  jobs.status {row['status']}: {row['c']}")
    for row in conn.execute("SELECT level, COUNT(*) c FROM jobs GROUP BY level"):
        print(f"  匹配度 {row['level']}: {row['c']}")
    print("\n最近 5 次运行（事件计数）：")
    for row in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5"):
        print(f"  {row['ran_at']} [{row['mode']}] 抓取 {row['fetched']} "
              f"新增 {row['new_count']} 更新 {row['updated_count']} "
              f"重开 {row['reopened_count']} 疑似下架 {row['closed_count']} 重复 {row['dup_count']}")


def cmd_recent(args):
    conn = connect()
    init_db(conn)
    since = (datetime.now() - timedelta(days=args.days)).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT * FROM jobs WHERE first_seen >= ? ORDER BY first_seen DESC", (since,)
    ).fetchall()
    print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="岗位增量库（URL+描述精准去重 + 增量事件）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    f = sub.add_parser("filter", help="从 stdin 读岗位 JSON，输出变化岗位")
    f.add_argument("--dry-run", action="store_true")
    f.add_argument("--missing-threshold", type=int, default=DEFAULT_MISSING_THRESHOLD,
                   help="连续多少次完整检索搜不到才判定疑似下架（默认 3）")

    m = sub.add_parser("mark", help="标记岗位状态（jobs 级，轻量）")
    m.add_argument("--url")
    m.add_argument("--company")
    m.add_argument("--status", required=True,
                   choices=["new", "pushed", "applied", "ignored",
                            "interviewing", "closed"])

    a = sub.add_parser("apply", help="记录 / 更新投递进度（applications 表）")
    a.add_argument("--url")
    a.add_argument("--link")
    a.add_argument("--company")
    a.add_argument("--title")
    a.add_argument("--city")
    a.add_argument("--note")
    a.add_argument("--applied-at")
    a.add_argument("--status", required=True, choices=APPLY_STATES)

    sub.add_parser("applications", help="列出全部投递进度")
    sub.add_parser("app-stats", help="投递进度统计")
    sub.add_parser("stats")
    r = sub.add_parser("recent")
    r.add_argument("--days", type=int, default=7)

    args = p.parse_args()
    if args.cmd == "init":
        conn = connect()
        init_db(conn)
        print(f"已初始化：{os.path.abspath(DB_PATH)}")
    elif args.cmd == "filter":
        cmd_filter(args)
    elif args.cmd == "mark":
        cmd_mark(args)
    elif args.cmd == "apply":
        cmd_apply(args)
    elif args.cmd == "applications":
        cmd_applications(args)
    elif args.cmd == "app-stats":
        cmd_app_stats(args)
    elif args.cmd == "stats":
        cmd_stats(args)
    elif args.cmd == "recent":
        cmd_recent(args)


if __name__ == "__main__":
    main()
