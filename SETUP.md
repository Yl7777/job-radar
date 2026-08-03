# 岗位雷达 · 安装与配置指南（SETUP）

给拿到本仓库的人。按下面走，半小时内能跑起每日自动推送。

> 前置：已安装 **WorkBuddy**（任意支持 skill 的 AI 工具也可，本指南以 WorkBuddy 为例）
> 且本机有 **Python3**（jobstore.py / report.py 只用标准库，无需 pip install）。

---

## 一、安装 skill

### 方式 A：从 GitHub 克隆后一键安装（推荐）

```bash
git clone <本仓库的 GitHub 地址> job-radar
cd job-radar
bash install.sh
```

`install.sh` 会自动检测 WorkBuddy，把本 skill 装到
`~/.workbuddy/skills/job-radar`（Windows 为 `C:\Users\你的用户名\.workbuddy\skills\job-radar`）。
安装后**重启/刷新** WorkBuddy，用大白话即可触发，例如：
「帮我搜一下上海 AI 产品运营的实习岗」。

### 方式 B：让 WorkBuddy 自己装

把 GitHub 链接发给 WorkBuddy，说：
「clone 这个仓库并运行里面的 install.sh 安装 job-radar skill」。
它会在你的机器上完成克隆与安装。

---

## 二、初始化你的个人检索配置

仓库**不含**任何人的私人配置（已写入 `.gitignore`）。你需要建立自己的：

**方法 1（零配置，推荐）：跑交互问答**
```bash
python scripts/brief.py
```
依次填写：① 数据保存路径（默认 `~/.job-radar`，可改为如 `D:/岗位雷达` 的任意文件夹）② 简历（核心输入）③ 实习/校招/社招 ④ 城市 ⑤ 方向 ⑥ 本次检索平台（含登录墙平台，直接 site: 公开快照检索，不要求先登录）。
脚本会生成 `prefs.json` 与 `prompt.txt`，并把你选的保存路径记下来，后续脚本自动沿用。

**方法 2（手写）：复制模板**
```bash
cp references/config.example.md profile/search-config.md
```
按注释填你的方向、城市、关键词组等。

> 求职类型 / 城市 / 方向都是**各人自己选**，互不影响。

---

## 三、绑定推送渠道

推送配置写在 `profile/push-config.md`（首次需自己建）：
```bash
cp references/push-config.example.md profile/push-config.md
```
然后按文件内注释启用渠道（微信 / 邮件 / webhook）。

### 渠道一：微信（手机收日报，推荐）

1. 在 WorkBuddy 设置里连 **「微信助理集成」**（扫码授权）。
2. 确认状态显示「已连接」。
3. 在 `profile/push-config.md` 把「渠道一：微信」标记为**已启用**。

> 微信不渲染 Markdown，日报已按纯文本排版（见 `automation-prompt.example.md` 约束 8）。
> 注意：微信渠道需你**偶尔从微信发条消息保持活跃**，否则可能收不到自动推送。

### 渠道二：邮箱（Agent Mail，可选备份）

1. 在 WorkBuddy 连 **Agent Mail** 连接器。
2. 在 `push-config.md` 填上你的收件地址，标记已启用。

### 渠道三：企业微信 / 飞书群机器人（可选）

在 `push-config.md` 填 webhook 地址即可，无需连连接器。

### 渠道四：本地日报（默认开启）

报告自动生成在 `reports/YYYY-MM-DD.html` 与 `.xlsx`，无需配置。

---

## 四、创建每日自动化

打开 WorkBuddy 的「自动化」，参考本仓库 **`automation-prompt.example.md`**：

1. **每日检索**任务：复制「任务一 / daily 模式」整段 prompt，`{JOB_RADAR_DIR}`/`{USER_NAME}`/`{DIRECTION}` 换成你的值，
   任务时间设 **08:00**，工作目录(cwd) 设为 `{JOB_RADAR_DIR}`。

> 该任务已**把登录墙平台（BOSS/猎聘/智联/51job/脉脉）的公开快照一并检索**，结果标「⚠️ 需手动复核」并附再检索线索，
> 无需单独的"登录提醒"任务。任务依赖 `push-config.md` 的「渠道一：微信 = 已启用」，先完成第三步再建任务。

---

## 五、登录墙平台怎么办（BOSS/猎聘/智联/51job/脉脉）

这些平台依赖登录态才能看完整 JD 与投递，但**公开快照可被 WebSearch 直接索引**。
每日 08:00 的检索**已经把它们的公开快照一并搜了**，搜到的岗位标「⚠️ 需手动复核」并附再检索线索
（岗位名 / 帖子标题 / 作者 / 发送时间 / 来源），你拿这些线索在对应 App 内确认在招并投递即可。
**本 skill 不登录任何平台、不要求你先登录**，所以没有"先登录再提醒"的环节。详见 `references/recheck-platforms.md`。

---

## 六、注意事项

- **去重库每人独立**：`data/` 已被 `.gitignore` 排除，每人克隆后首次运行自��建库，互不串数据。
- **个人配置不进仓库**：`profile/search-config.md`、`profile/push-config.md`、`prefs.json`、运行产物均不入库，
  分享仓库不会泄露你的方向、城市、webhook 等隐私。
- **微信活跃度**：长时间不说话可能导致自动推送不来，每天 08:00 前从微信随便说句话即可。
- 登录墙平台（BOSS/猎聘/智联/51job/脉脉）的岗位为公开快照检索结果，AI 无法确认是否仍在招，投递前请在对应 App 内用报告里的再检索线索自行确认在招。

---

## 七、常见问题

**Q：微信收不到推送？**
A：检查「微信助理集成」是否「已连接」；当天是否从微信发过消息（激活渠道）；`push-config.md` 渠道一是否「已启用」。

**Q：想改推送时间？**
A：在自动化里改 `BYHOUR`/`BYMINUTE`（或直接改任务时间）即可。
