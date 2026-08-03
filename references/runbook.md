# 运行手册（RUNBOOK）

岗位雷达（job-radar）是一套「中国大陆岗位检索 + 独立质检 + 精准去重 + Excel/HTML 报告」工具。
本仓库只含**可移植内核**：任何带 Python3 的机器、任何有联网检索能力的 AI 助手都能用，
**不绑定任何特定平台或调度器**。

> 设计原则：宁多勿少、全面、真实、幻觉低、匹配度高；只覆盖中国大陆岗位。

---

## 0. 目录结构

```
job-radar/
├── SKILL.md                核心提示词（AI 加载它）
├── README.md
├── LICENSE                 MIT
├── install.sh              一键安装到各 AI 工具的 skills 目录
├── .gitignore
├── references/
│   ├── platforms-cn.md     中国大陆全量平台注册表（类型 / 是否需登录 / 搜索语法 / 下架标志语）
│   ├── recheck-platforms.md  登录墙平台的公开快照检索与再检索指引
│   ├── verified-official-sources.md  已人工核验的官方招聘域名清单（季度复核）
│   ├── company-classification.md  公司分类规范（company_tag 标签枚举）
│   ├── excel-export.md     Excel 列结构与格式
│   ├── runbook.md          本文件（执行手册）
│   └── config.example.md   想手写检索配置的参考模板（非必需）
├── scripts/
│   ├── brief.py            交互式问答 → 生成 prefs.json 与 prompt.txt（含简历与平台选择）
│   ├── run.py              一键入口：串联 问答→(AI检索)→去重→报告
│   ├── jobstore.py         岗位增量库（URL+描述 精准去重 + 增量事件 + 投递进度，纯标准库）
│   ├── report.py           渲染本地 Excel 表格（附链接、变化/公司类型列、疑似下架分区）+ HTML 报告
│   └── send_notifications.py  便携通知发送器（SMTP 邮件 + 企业微信，纯标准库）
└── templates/
    └── report.html         HTML 报告模板（report.py 读取并填充）
```

## 1. 零配置用法（推荐，不懂代码也能用）

1. 运行入口：`python scripts/run.py`。
2. 第一次会进入中文问答：
   - **先问简历**（核心输入）：文件路径 / 粘贴文本 / 无简历则口述背景；
   - 选 实习/校招/社招、城市、方向、硬性要求；
   - **确认本次检索平台**（免登录平台与登录墙平台都直接 `site:` 公开快照检索；登录墙平台结果标「⚠️ 需手动复核」）。
   自动生成 `prefs.json` 和 `prompt.txt`。
3. 打开 `prompt.txt`，把内容完整发给你的 AI 助手，让它返回一段岗位 JSON。
4. 把 AI 返回的 JSON 保存为 `jobs_raw.json`，重新运行 `python run.py`。
5. 脚本自动去重，并在 `reports/` 生成 **Excel 表格（链接可点击）+ HTML 报告**，浏览器打开即可看。

全程**不编辑任何配置文件、不安装任何依赖**。

## 2. 手动进阶用法

- 直接写检索需求：参考 `references/config.example.md`，可跳过问答、手写 `prefs.json`（含 `resume_path` / `platforms` 字段）。
- 去重库命令：
  - `python scripts/jobstore.py init`        初始化数据库
  - `python scripts/jobstore.py filter < jobs_raw.json`  过滤出本期变化并入库
  - `python scripts/jobstore.py filter --missing-threshold 3 < jobs_raw.json`  自定义疑似下架阈值
  - `python scripts/jobstore.py stats`        查看库统计（含事件计数）
  - `python scripts/jobstore.py mark --url <链接> --status applied`  标记岗位状态（轻量）
  - `python scripts/jobstore.py apply --url <链接> --status 已投递 --note "8/1投递"`  记录投递进度
  - `python scripts/jobstore.py applications`  列出全部投递进度
  - `python scripts/jobstore.py app-stats`  投递进度统计
  - `python scripts/jobstore.py recent --days 7`  查看近 7 天新增
- 生成报告：`python scripts/report.py new_jobs.json`（同时产出 .xlsx 与 .html）
- 发送通知：`python scripts/send_notifications.py --report reports/report-YYYY-MM-DD.xlsx --new-jobs new_jobs.json --channel all`
  （环境变量配置 SMTP_* / WECHAT_WEBHOOK；`--dry-run` 仅校验）

## 3. 完整检索流程（对应 SKILL.md）

1. **简历核心输入**：读简历（文件或文本），提取画像；无简历才口述。
2. **确认求职类型 / 城市 / 方向 / 硬性要求**。
3. **确认检索平台（搜索前门禁）**：
   - **默认全选 `references/platforms-cn.md` 列出的所有平台（含登录墙）**，仅当用户明确要求时剔除个别；不得默认「只选几个」——本 skill 的宗旨是全面覆盖、替用户省去自己检索的时间。
   - 免登录平台默认可选，直接 WebSearch。
   - 登录墙平台（BOSS/猎聘/智联/51job/脉脉）**同样直接 `site:` 公开快照检索**，不进入登录流程、不要求用户先登录；结果标「⚠️ 需手动复核」并填全再检索线索。详见 `references/recheck-platforms.md`。
4. **生成检索指令**：`brief.py` → `prompt.txt`（含简历画像、平台、after:30 时效要求）。
5. **强制遍历全平台执行搜索**：**不得预筛平台**——`references/platforms-cn.md` 第一~五节列出的**每一个 ✅ 免登录源 + 第四节全部 5 个登录墙平台（BOSS/猎聘/智联/51job/脉脉）都要发起检索**，统一套用第六节「固定 query 模板」。免登录与登录墙平台都直接 WebSearch `site:` 公开快照检索；登录墙平台结果标「⚠️ 需手动复核」并填全再检索线索。城市只作为 query 维度扩展，不作为跳过平台的理由。详见 `references/recheck-platforms.md`。
6. **独立质检 subagent（强制）**：🟢 全量并行链接验活（下架标志语见 platforms-cn.md 第八节）、🟡 抽查 20-30%、去重复核（同公司同名不同描述必须保留多条）、数据完整性。
7. **去重（只推变化）**：`jobs_raw.json` → `jobstore.py filter`（URL 主键 + 描述辅助键）。
   识别出四类变化事件：新增 / 更新（JD 变化）/ 重开（曾下架又出现）/ 疑似下架（连续 3 次搜不到）。
   输出 `new_jobs.json` 仅含本期变化，每条带 `_event` 字段。
8. **报告**：`report.py` 生成 Excel（主，含"变化 / 公司类型"列 + 疑似下架浅红分区）+ HTML（补充）。
9. **（可选）通知**：`send_notifications.py` 把变化摘要 + Excel 通过邮件 / 企业微信发出（纯标准库）。

## 4. 平台与检索说明（全部直接 `site:` 公开快照检索，不登录）

- **免登录平台**：实习垂类、官方/公共渠道、企业官网（大厂/中小厂/AI 公司/出海）、综合平台公开页、V2EX/掘金/公众号。
  能被 WebSearch 直接检索，默认启用。详见 `references/platforms-cn.md` 第一~五节。
- **登录墙平台（同样直接搜）**：BOSS 直聘、猎聘、智联、前程无忧 51job、脉脉等依赖登录态 / cookies 才能看完整 JD 与投递，
  但**公开快照仍可被 WebSearch 直接索引**（如 `site:zhipin.com` / `site:liepin.com` 能返回标题、薪资、公司、部分 JD 摘要）。
  做法：对登录墙平台**直接 `site:` 公开快照检索**，搜到的公开结果纳入清单，逐条标注「⚠️ 需手动复核」并填全再检索线索（岗位名 / 帖子标题 / 作者 / 发送时间 / 来源）；
  **不进入任何登录流程、不处理 cookies、不要求用户先登录**。完整确认在招与投递由用户在自己已登录的 App 内完成。详见 `references/recheck-platforms.md`。

## 5. 去重原理（为什么不用"指纹"）

旧版用 `(公司 + 岗位名 + 城市)` 做哈希指纹，会把同一家公司"同名不同岗"误合并。本版改为：

1. **主键 = 归一化链接**：剥离协议 / `www.` / fragment，并**只去掉已知跟踪参数**（`utm_*` / `from` / `spm` / `trace` / `ref` / `t` / `pcm` 等），保留真实查询参数（如岗位 id 在 query 里）。
   同一帖子被不同聚合站转载、或换来源参数重发，都判为同一岗位。
2. **辅助键 = 描述哈希**：仅在"同公司 + 同标题 + 描述文本高度一致"时判重，避免误并。
3. **无链接无描述**的纯快照 → 一律视为新岗位（宁可重复也不漏）。
4. **增量事件**（只推变化，不复发全量）：
   - `new`：URL 从未见过。
   - `updated`：`content_hash`（标题/公司/城市/薪资/描述/标签/匹配点 的归一化哈希）变化 → JD 或要求变了。
   - `reopened`：曾 `closed`（疑似下架）本次又出现。
   - `possibly_closed`：连续 `missing-threshold`（默认 3）次"完整检索却搜不到"才标记；**一次没搜到不误判下架**。
5. **投递进度独立成表**（`applications`）：与"岗位是否在招"分表，互不干扰。

这样：同公司同名不同岗一定保留；跨天同一帖子一定去重；每日只推送真正变化的部分。

---

## 6. 检索一致性与快照属性（约束不同 AI / agent 的结果方差）

本 skill 用自然语言 WebSearch / WebFetch 检索，**结果天然带方差**（搜索引擎实时波动、模型 query 构造差异、登录墙验活概率性）。为逼近「每日尽可能多地推送真实新增」，强制以下三条：

1. **固定 query 模板**：所有平台套用 `references/platforms-cn.md` 第六节第 6 点的模板，不自由发挥省略维度；城市按 `preferred_cities` 逐城展开。
2. **固定去重库路径**：每次运行前 `export JOBRADAR_HOME=<本仓库目录>`（如 `C:/Users/Better/WorkBuddy/2026-07-31-14-36-38/job-radar`），**确保每次落在同一 SQLite 库**，避免「有时新建库→全部算新增、有时复用旧库→全部算重复」的视图错乱。各副本（含 friends/*）用各自目录，互不串库。
3. **快照属性（固化认知）**：链接验活是**快照**不是保质期——报告必须带验活时间戳，隔天重跑结果会变化（尤其登录墙平台）。**每日固定重跑一次**即是正确的增量来源；不要指望一次检索覆盖永久。新增岗位来自「本次搜到、且库里没见过」的子集，因此「全面遍历 + 稳定库 + 每日重跑」三者缺一不可。
