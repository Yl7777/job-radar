# 中国大陆求职平台注册表

> 本文件是 `job-radar` 的"平台字典"。搜索时按 `config.example.md` 选定的
> **求职类型**（实习 / 校招 / 社招）和 **检索平台** 从这里取站点与语法。
>
> **免登录平台**（"免登录"列 = ✅）能被 WebSearch 直接索引，无需任何登录态或 cookies，默认启用。
> **登录墙平台**（列标注 ❌ / ⚠️弱）指 BOSS/猎聘/智联/51job/脉脉等依赖登录态才能看完整 JD 的平台——
> 但它们的**公开快照仍可被 WebSearch 直接索引**，因此**同样直接 `site:` 公开快照检索**，不进入任何登录流程；
> 搜到的公开结果标「⚠️ 需手动复核」并附再检索线索，由用户在自己已登录的 App 内确认在招。详见 `references/recheck-platforms.md`。

图例：
- 类型：实习 / 校招 / 社招 / 通用
- 免登录：✅ = 可被 WebSearch 直接索引，默认启用；⚠️弱 = 仅公开快照可被索引、需手动复核；❌* = 登录墙，仍走 `site:` 公开快照检索（标需手动复核），不登录
- 站点语法：`site:域名` 形式，直接拼进 WebSearch 查询

---

## 一、实习垂类（实习为主，校招也有）

| 平台 | 类型 | 免登录 | 站点语法 / 检索方式 | 备注 |
|------|------|--------|---------------------|------|
| 实习僧联盟站（rc114） | 实习 | ✅ | `site:league.rc114.com 关键词 城市` | 实习僧官方联盟分发站，索引好，**实测有效**，优先于本站 |
| 应届生求职网 | 实习/校招 | ✅ | `site:yingjiesheng.com 关键词 城市` | 校招+实习聚合，**实测有效** |
| 牛客校招（牛企直聘） | 实习/校招 | ✅ | `site:campus.niuqizp.com 关键词 城市` | 聚合各公司官网校招，**实测有效** |
| 牛客网（内推帖） | 实习/校招 | ✅ | `site:nowcoder.com 关键词 实习 内推` | 内推帖多，带真实 JD 链接 |
| 海投网 | 实习/校招 | ✅ | `site:haitou.cc 关键词 城市` | 校招宣讲会+实习 |
| 刺猬实习 | 实习 | ✅ | `site:ciweishixi.com 关键词 城市` | 名企实习、远程实习 |
| 实习僧（本站） | 实习 | ⚠️弱 | `site:shixiseng.com 关键词` | **实测主站索引极差**，基本搜不到；改用联盟站 |
| 校招网 / 校联帮 | 校招 | ✅ | `site:xiaozhao.com 关键词 城市` | 校招资讯聚合 |
| 海角实习 / 简寻 | 实习 | ✅ | `site:jianxun.com 关键词` | 补充 |

---

## 二、官方 / 公共渠道（质量最高，优先）

| 平台 | 类型 | 免登录 | 站点语法 / 检索方式 | 备注 |
|------|------|--------|---------------------|------|
| 国聘（央企校招） | 校招/社招 | ✅ | `site:gptalent.com 关键词` / `site:special.cbimc.cn 关键词` | 央企/国企，质量高 |
| 中国公共招聘网（人社部） | 通用 | ✅ | `site:job.mohrss.gov.cn 关键词 城市` | 官方，岗位真实 |
| 教育部 24365 校园招聘 | 校招 | ✅ | `site:job.ncss.cn 关键词` | 官方校招平台 |
| 各高校就业网 | 校招 | ✅ | `site:<学校域名>/career 关键词` 例：`site:career.tsinghua.edu.cn 实习` | 清北复交浙等，JD 最完整 |
| 企业官方招聘官网（见第三节） | 实习/校招/社招 | ✅ | `site:<官网域名> 关键词 实习` | **质量最高，强烈建议纳入** |

---

## 三、大厂 / 中小厂 / AI 公司 / 出海 官方招聘官网（校招+实习+社招全含）

直接 `site:` 这些域名，JD 最完整、最真实、无中介、全免登录（✅ 可直接 WebSearch 检索）。
**全面覆盖原则：所有在本节列出的官网域名都应纳入检索，不得因"只选几个"而遗漏。** 候选源虽多，但多搜一组 query 的成本极低、漏掉一个真岗的损失极高——本 skill 的宗旨是「全面、真实、替用户省去自己检索的时间」，因此默认全跑；仅当用户明确要求精简时再按需收敛。

**互联网大厂**
- 字节跳动 `site:job.bytedance.com 关键词`
- 腾讯 `site:join.qq.com 关键词` / `site:tencentschool.com 关键词`（校招）
- 阿里巴巴 `site:talent.alibaba.com.cn 关键词`
- 美团 `site:zhaopin.meituan.com 关键词`
- 百度 `site:campus.baidu.com 关键词` / `site:talent.baidu.com 关键词`
- 京东 `site:campus.jd.com 关键词`
- 拼多多 `site:campus.pinduoduo.com 关键词`
- 滴滴 `site:didiglobal.com/campus 关键词`
- 网易 `site:campus.163.com 关键词`
- 快手 `site:kuaishou.com/z 关键词`
- 小红书 `site:job.xiaohongshu.com 关键词`
- B站（哔哩哔哩）`site:bilibili.com/hr 关键词`
- 小米 `site:mi.com/careers 关键词`

**互联网知名中小厂（垂类头部 / 独角兽，校招与实习机会多）**
- 知乎 `site:zhihu.com/careers 关键词`
- 携程 `site:careers.ctrip.com 关键词` / `site:campus.ctrip.com 关键词`（校招）
- 唯品会 `site:vip.com/careers 关键词`
- Keep `site:keep.com/careers 关键词`
- 得物（毒）`site:dewu.com 关键词`
- Soul `site:soulapp.cn 关键词`
- 喜马拉雅 `site:ximalaya.com/careers 关键词`
- 阅文集团 `site:yuewen.com/careers 关键词`
- 金山办公（WPS）`site:wps.cn/careers 关键词`
- 微博 `site:job.weibo.com 关键词`
- 同花顺 `site:10jqka.com.cn 关键词`
- 东方财富 `site:eastmoney.com/careers 关键词`
- 完美世界（游戏）`site:wanmei.com/careers 关键词`
- OPPO `site:oppo.com/careers 关键词`
- vivo `site:vivo.com.cn/careers 关键词`
- 荣耀 `site:honor.com/careers 关键词`
- 贝壳（房产科技）`site:ke.com/careers 关键词`
- 猿辅导 `site:yuanfudao.com 关键词`
- 好未来（学而思）`site:tal.com/careers 关键词`
- 大疆（DJI）`site:dji.com/careers 关键词`
- 第四范式（企业 AI）`site:4paradigm.com/careers 关键词`
- 旷视（计算机视觉）`site:megvii.com 关键词`
- 寒武纪（AI 芯片）`site:cambricon.com 关键词`
- 地平线（自动驾驶）`site:horizon.ai/careers 关键词`
- 小马智行（Pony.ai）`site:pony.ai/careers 关键词`
- 文远知行（WeRide）`site:weride.ai/careers 关键词`

**AI 公司（大模型 / AIGC —— 头部 + 其他知名玩家）**
- 头部 / "AI 六小龙"：
  - 月之暗面（Kimi）`site:moonshot.cn/careers 关键词`
  - MiniMax `site:minimax.io/careers 关键词`
  - 智谱 AI `site:zhipuai.cn/career 关键词`
  - 深度求索（DeepSeek）`site:deepseek.com 关键词`
  - 百川智能 `site:baichuan-ai.com 关键词`
  - 零一万物 `site:01.ai 关键词`
  - 商汤 `site:sensetime.com/career 关键词`
- 其他知名 AI 公司（同样值得纳入）：
  - 阶跃星辰 `site:stepfun.com 关键词`
  - 面壁智能 `site:modelbest.cn 关键词`
  - 百图生科（BioMap）`site:biomap.com 关键词`
  - 生数科技（Vidu）`site:shengshu-tech.com 关键词` / `site:vidu.com 关键词`
  - 爱诗科技（PixVerse）`site:pixverse.ai 关键词`
  - 硅基流动（SiliconFlow）`site:siliconflow.cn 关键词`
  - 秘塔科技（Metaso）`site:metaso.cn 关键词`
  - 中科闻歌 `site:wenge.com 关键词`
  - 深言科技 `site:shenyan.ai 关键词`
  - 稀宇科技、元象、MiniMax 海外等：直接 `site:<官网>/career 关键词`

**科技出海公司（中国背景、主做海外市场，产品/运营/本地化岗位多）**
- SHEIN（希音）`site:careers.shein.com 关键词`
- 米哈游（HoYoverse）`site:mihoyo.com/careers 关键词` / `site:hoyoverse.com/careers 关键词`
- 莉莉丝游戏（Lilith）`site:lilithgames.com/careers 关键词`
- 叠纸游戏 `site:papergames.cn/careers 关键词`
- 鹰角网络（Hypergryph）`site:hypergryph.com/careers 关键词`
- 心动网络（TapTap）`site:taptap.cn/careers 关键词`
- 安克创新（Anker）`site:careers.anker.com 关键词`
- 影石 Insta360 `site:insta360.com/careers 关键词`
- 传音控股（非洲手机）`site:transsion.com/careers 关键词`
- 昆仑万维（出海 AI/游戏）`site:kunlun.com/careers 关键词`
- 万兴科技（Wondershare）`site:wondershare.com/careers 关键词`
- 声网（Agora，RTC）`site:agora.io/careers 关键词`
- 赤子城科技（社交出海）`site:cmcm.com 关键词`
- 易点天下（Yeahmobi，出海营销）`site:yeahmobi.com/careers 关键词`
- 涂鸦智能（IoT 出海）`site:tuya.com/careers 关键词`
- Bigo（欢聚时代）`site:bigo.tv/careers 关键词`
- 富途证券（Futu，金融科技出海）`site:futuholdings.com/careers 关键词`
- 蔚来 `site:nio.com/careers 关键词`
- 小鹏 `site:xiaopeng.com/careers 关键词`
- 理想 `site:lixiang.com/careers 关键词`

> 提示：很多公司官网是 `*/careers` 或 `*/campus`，搜不到时换根域名再试；
> 中小厂与出海公司的实习/校招页常随季度更新，建议纳入检索范围以提升覆盖面。

---

## 四、综合招聘平台（社招为主，部分可被索引）

| 平台 | 类型 | 免登录 | 站点语法 | 备注 |
|------|------|--------|----------|------|
| BOSS 直聘 | 通用 | ❌* | `site:zhipin.com 关键词 城市` | 登录墙，但公开快照可索引；**直接 `site:` 搜，标「⚠️ 需手动复核」**，完整 JD/投递由用户 App 内确认 |
| 猎聘 | 社招 | ❌* | `site:liepin.com 关键词 城市` | 中高级，登录墙；公开快照可索引，直接搜 + 标需手动复核 |
| 智联招聘 | 通用 | ⚠️弱 | `site:zhaopin.com 关键词 城市` | 部分公开页可被索引；直接搜，标需手动复核 |
| 前程无忧 51job | 通用 | ⚠️弱 | `site:51job.com 关键词 城市` | 部分公开页可被索引；直接搜，标需手动复核 |
| 脉脉 | 社招/内推 | ❌* | `site:maimai.cn 关键词` | 人脉+内推，登录墙；公开快照可索引，直接搜 + 标需手动复核 |
| 看准网 | 通用(评价) | ✅ | `site:kanzhun.com 公司名` | 用于查公司口碑/薪资，不做岗位源 |
| 外企在华校招官网 | 校招 | ✅ | `site:<公司>/campus-cn 关键词` | 微软/谷歌/亚马逊/英伟达 等中国校招页 |

> 标注 ❌* 的平台（BOSS/猎聘/脉脉）指"依赖登录态才能看完整 JD 与投递"，但**公开快照仍可被 WebSearch 索引**，因此**同样直接 `site:` 检索、标「⚠️ 需手动复核」**，不进入登录流程。详见 `references/recheck-platforms.md`。

---

## 五、内容平台 / 社区（补充线索，弱索引）

| 平台 | 类型 | 免登录 | 检索方式 | 备注 |
|------|------|--------|----------|------|
| 微信公众号招聘推文 | 实习/校招 | ⚠️弱 | `site:mp.weixin.qq.com 关键词 实习 招聘 城市` | 弱索引，作为补充 |
| V2EX 招聘帖 | 通用 | ✅ | `site:v2ex.com 关键词 招聘` | 技术社区招聘节点，岗位偏互联网/出海 |
| 掘金社区招聘 | 通用/技术 | ✅ | `site:juejin.cn 关键词 招聘` | 程序员/技术岗招聘帖，偏开发/算法 |
| 小红书招聘笔记 | 实习 | ⚠️弱 | `site:xiaohongshu.com 关键词 招聘` 或 App 内搜 | 公开页偶尔可索引，直接搜 + 标需手动复核；量大时建议 App 内补搜 |
| 豆瓣小组 / 微博超话 | 实习 | ⚠️弱 | App 内搜索为主 | 零散，公开快照偶尔可索引，标需手动复核 |

---

## 六、检索语法约定（写入 search-config 关键词组）

1. **实习**：每组关键词必须带 `实习 / 实习生 / intern / 暑期 / 日常实习` 之一，
   否则会被社招淹没。
2. **校招**：带 `校招 / 2027届 / 应届 / 秋招 / 春招 / 校园招聘`。
3. **社招**：带 `招聘 / 急聘 / 社招` 或直接岗位名 + 城市。
4. 时效：每组追加 `after:<30天前日期>`（仅主流搜索引擎支持，rc114/牛客等
   不支持的站点不强求）。
5. 城市维度：关键词 × 城市展开，密度高的城市（上海/杭州/深圳/北京）搜前 2 页，
   其余城市搜第 1 页。**城市是 query 的展开维度，不是平台 / 公司的排除维度——不得因「某平台 / 公司岗位偏其他城市」就跳过对其的检索。**
6. **固定 query 模板（强制基线，约束不同 AI / agent 的检索一致性）**：为避免不同模型、不同次运行构造的 query 差异导致覆盖忽多忽少，所有平台检索**至少**统一套用以下模板作为最低基线：
   - 企业官网 / 实习垂类 / 公共渠道：`site:<域名> <方向关键词> <实习/校招/社招词> <城市> after:<30天前日期>`
   - 登录墙平台：`site:<域名> <方向关键词> <实习/校招/社招词> <城市>`（登录墙快照检索不强求 `after:`）
   - 通用兜底（不限定域名）：`<方向关键词> <实习/校招/社招词> <城市> 招聘 2026`
   - 其中「城市」必须按用户 `preferred_cities` **逐城展开**（如「上海 杭州 广州 深圳 珠海」各发一组）；城市只用于限定 query，**绝不用于预先跳过某个平台 / 公司**——某公司在用户目标城市无岗，搜出来是空结果属正常，不应反过来「因城市不符就不搜这家公司」。
   - ⚠️ **模板是地板，不是天花板**：模板保证不同 AI 结果一致，但**不得因套了模板就只发这一条**。见第 7 点补变体规则，避免漏搜。
7. **补变体，防漏搜（强制）**：当某平台 / 方向按模板检索返回结果稀疏（如 < 5 条或大量不相关），**必须追加变体 query 而非放弃该平台**：
   - 换岗位名词：加 / 换近义词（如「产品运营」↔「产品助理」↔「商业运营」↔「增长运营」）；
   - 换城市组合：拆开逐城、或去掉城市限定再筛；
   - 放宽时效：去掉 `after:` 限定看更早但可能仍有效的岗；
   - 换检索形态：对登录墙平台尝试「平台名 + 方向 + 城市」措辞（更易命中公开快照页）；
   - 多源互证：同一岗位在多个平台出现时优先保留。
   - **原则：宁多发 query 不漏平台；模板是保底一致性，变体是保覆盖广度。**
8. **平台列表动态扩展（自发现 → 确认 → 入列）**：检索过程中若 AI 自行发现 `platforms-cn.md` 未收录、但**真实可靠**的招聘源（如某公司的官方招聘页、新的聚合站、垂直社区），应：
   - **先记录**：把发现的源（域名 / 名称 / 发现场景 / 为何可靠：如能稳定返回真实在招岗位、非中介、无虚假）暂存到本文件末尾的「候选新增平台」列表；
   - **再确认**：在当次报告或对话中向用户提出，经用户确认无误后再**正式写入**对应分类（实习垂类 / 官方 / 内容社区等）；
   - **不擅自入库**：未经用户确认的新源不得直接当成已收录平台使用，避免误收水站 / 中介站污染结果。
   - 目的：让搜索范围随使用**越来越全面**，而非一次性写死。

---

## 七、登录墙平台的处理原则（直接公开快照检索，不登录）

- **所有平台一律直接 `site:` 公开快照检索**：实习垂类、官方/公共渠道、企业官网、综合平台公开页、登录墙平台（BOSS/猎聘/智联/51job/脉脉）都走同一条 WebSearch 流水线，**不进入任何登录流程、不要求用户先登录**。
- **登录墙平台照常搜**：BOSS/猎聘/智联/51job/脉脉 的公开快照可被搜索引擎索引，能拿到标题、薪资、公司、部分 JD 摘要，足够做匹配初判；**不要因为"需要登录"就跳过**。
- **标「⚠️ 需手动复核」**：登录墙平台搜到的岗位，JSON 里 `needs_recheck` 置 true，并填全再检索线索（岗位名 / 帖子标题 / 作者 / 发送时间 / 来源）。报告会显式标「⚠️ 需手动复核」并附再检索线索块，完整确认在招与投递由用户在自己已登录的 App 内完成。
- **不登录、不索要凭证**：本 skill 不内置自动登录、不处理 cookies、不索要账号密码；登录墙链接的验活会落 `unknown`/`unsure`，由报告统一标「⚠️ 需手动复核」。详见 `references/recheck-platforms.md`。

---

## 八、岗位下架标志语（质检链接验活用）

质检阶段对**全部带链接的岗位**（不只 🟢）做验活时，访问链接后页面出现以下文案说明岗位已下架/过期，应直接移除：

- **前程无忧（51job）**：**「当前职位审核中或已下线」**+ 跳空搜索状态图 `search_empty.png` + 「重新搜索」按钮（**实测最高频，jobs.51job.com 的老链接大量命中，务必逐条查**）；旧版文案「很抱歉，你选择的职位目前已经暂停招聘」
- **实习僧**：职位描述上方标「当前职位已下线」——**JD 内容仍完整可见，极易误判为在招**，必须看顶部状态条
- BOSS 直聘：「职位已下线」「该职位已停止招聘」「职位已关闭」
- 拉勾：「该职位已下线」「职位已停止招聘」
- 猎聘：「职位已结束」「该职位已暂停招聘」
- 智联招聘：「职位已下线」「该职位已暂停」「该职位已结束招聘」「职位不存在」
- 通用信号：页面 404、自动跳转回搜索首页/职位列表页、岗位详情内容为空

**反向铁律（防误删）**：抓取失败、超时、登录墙、安全验证、内容为空但无失效文案 → 判 `unknown` 保留并标注，**不得判定为下架**。BOSS 直聘（zhipin.com）与猎聘移动端在无登录态下被安全验证拦截是常态，实测一批 BOSS 链接可能全部 `unknown`，这不代表岗位失效。

**易混淆的 `not_detail`（降级而非移除）**：
- 猎聘的 `/s/xxx/`、`/city-xx/xxx/`、`/zpxxx/` 形态是**搜索列表页**，不是岗位详情
- 爱企查（aiqicha.baidu.com）招聘知识库、脉脉（maimai.cn）发帖、新闻报道、公司官网首页 → 都不是岗位详情页
- 高校就业网的「批量招聘公告」（一帖罗列几十个岗位名）→ 不是详情页，且常带已过期的招聘时间段
- 实习僧联盟站 `league.rc114.com/Union/Company?uid=` 是公司页；`/Union/Position?jobId=` 才是岗位详情页

> 注意：以上文案可能随平台改版变化，判断标准是「页面是否还在正常展示该岗位的完整 JD 和投递入口」，而不是死磕字面匹配。
> 实习垂类、企业官网、高校就业网等无统一标志语，验活时以「能否打开真实 JD 详情页」为准。
> **另需检查页面 JD 里写的投递截止日期是否已过当前日期**——页面能正常打开不代表窗口还开着（如高校就业网公告常年挂着，招聘时间早已截止）。

---

## 九、链接形态黑名单（采集期 + 脚本静态判定共用）

`verify_links.py` 在发请求前先用 URL 形态做静态判定（零网络、零 token），把"一眼就不是岗位详情页"的链接直接判 `not_detail` 或 `unknown`。AI 在**采集期**也应参考同一套规则，优先存真详情页链接，从源头减少 `not_detail` 噪音。

**正向放行特征（命中即视为具体岗位页，交给 HTTP 层判定）：**
- 路径含 5 位以上纯数字 ID：`/170699160.html`、`job-008-017-068.html`
- 带前缀的 slug：`inn_xbre3s14mpci`（实习僧）、`job-vyU5zCLNa.html`（牛企直聘）
- 超长哈希 / token：`4280035b1f7ad2541XR72tS4FVI~.html`
- 查询参数带 ID：`?postId=1234567890`、`?jobId=xxx`

**黑名单形态（命中即 `not_detail`，无需请求）：**
- **站点主页**：`domain.com/`、`/index`、仅 `#` 锚点无路径
- **搜索 / 列表 / 公司页**：`/search`、`/s/`、`/so`、`/list`、`/joblist`、`/zhaopin`、`/company`、`/gongsi`、`/firm`、`/campus`、`/careers`、`/jobs`、`/positions` 且无具体 ID；带 `?keyword=` / `?q=` / `?query=` / `?kw=` 等搜索参数
- **无岗位 ID 的招聘平台路径**：已知平台（zhipin / liepin / zhaopin / 51job / lagou / shixiseng / ciweishixi / rc114 / nowcoder / niuqizp 等）链接里找不到数字 / 哈希 ID → 高概率列表页
- **第三方资讯 / 工商站（永远不是岗位详情页）**：maimai.cn、aiqicha.baidu.com、qcc.com、qichacha.com、tianyancha.com、zhihu.com、csdn.net、jianshu.com、cnblogs.com、juejin.cn、微信公众号 / 百家号、sohu / 163 / sina / 头条、小红书 / 抖音 / 豆瓣 / B站 帖

**反爬 / 挑战落点（命中即 `unknown`，绝不判 dead）：**
- `_waf_`、`__jsl_clearance`、`acw_sc__v2`、`security_verify`、`checking your browser`、`nocaptcha` —— 说明拿到的是加密挑战页而非真实 JD（51job 的 WAF 加密页就长这样，正文一大坨密文却无任何岗位特征词）

**与脚本对齐**：上述规则在 `verify_links.py` 中对应 `LIST_PATH_RE` / `LIST_QUERY_RE` / `DETAIL_ID_RE` / `THIRD_PARTY_HOSTS` / `KNOWN_JOB_BOARDS` / `WALL_PATTERNS` 常量；改规则后务必跑 `python scripts/verify_links.py --selftest` 确认没改坏。

---

## 十、各平台验活穿透力（决定该抱多大期望）

2026-08 实跑测得。L1 = `verify_links.py` 脚本（urllib 直连），L2 = AI 的 WebFetch。

| 平台 | L1 脚本 | L2 AI WebFetch | 采集建议 |
|---|---|---|---|
| 牛客网 / nowpick | ⏳ JS 渲染，正文只有 ~370 字符无岗位特征 | ✅ 能拿到完整 JD | 放心收，L2 必能确证 |
| **51job / 前程无忧** | ⏳ WAF 返回 95KB 密文（`{"_waf_xxx":...}`） | ✅ **能穿透 WAF 拿到完整 JD** | 死链率最高但 L2 治得了，**必须做 L2** |
| 实习僧 / 牛企直聘 / 应届生求职网 | ✅ 多数可直接判定 | ✅ 补刀 | 优选来源 |
| 企业官网（美团 / 腾讯等） | ⏳ 多为 JS 渲染 | ✅ 通常可读 | 优选来源，时效最准 |
| **BOSS 直聘** | ⏳ 跳登录墙 | ❌ **只拿到登录/注册页** | 标「⚠️ 需手动复核」+ 再检索线索，交付时明说需 App 内确认 |
| **智联招聘 / 猎聘** | ⏳ 安全验证 / 登录墙 | ❌ 多数拿不到 | 标「⚠️ 需手动复核」+ 再检索线索；同岗若在牛客/实习僧/51job 有链接优先用那条 |

**实操结论：**

1. 采集时**同一岗位若在多平台出现，优先存 L2 能穿透的平台链接**（牛客 / 实习僧 / 51job / 企业官网），把 BOSS / 智联链接作为备选写进备注。这能直接把「无法确认」的比例压下去。
2. BOSS / 智联的 `unsure` 条目，交付时标「⚠️ 需手动复核」并在报告附再检索线索，兜底话术：「用公司名 + 岗位名（或帖子标题 / 作者 / 发送时间）在对应 App 内搜索确认」——比给一条打不开的链接有用。
3. 验活是**快照**，不是保质期。报告里必须带验活时间，隔天再用要重跑。

---

## 候选新增平台（AI 自发现 → 待用户确认后正式入列）

> 本区由 AI 在检索过程中**自动发现但未确认**的可靠招聘源暂存处。每条需写明：域名 / 名称 / 发现场景 / 为何可靠（稳定返回真实在招岗、非中介、无虚假）。**未经用户确认，不得当成已收录平台直接使用。** 用户确认后，由 AI 将其归入上方相应分类（实习垂类 / 官方 / 内容社区等）并从本区移除。

| 待确认源 | 域名 | 发现场景 | 为何可靠（暂记） | 状态 |
|---|---|---|---|---|
| _（示例占位，待实际发现后填写）_ | | | | 待确认 |
