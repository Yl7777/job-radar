# 已核验官方招聘来源（Verified Official Sources）

本文件维护一份**已人工核验、可放心直接检索**的中国大陆企业官方招聘渠道清单。
用途：当某岗位只在聚合站 / 转载页出现时，优先回到这里的「官方域名」二次核验，
降低拿到失效链接或钓鱼页面的概率。

> 复核周期：**每季度第一个月**人工复核一次（检查域名是否变更、是否新增子公司招聘站）。
> 上次复核：2026-07。

## 使用约定

- 「官网」指企业**自有**招聘域名，不是第三方聚合站（实习僧 / BOSS / 猎聘等）。
- 检索时优先用官网的「搜索 / 校园招聘 / 社会招聘」入口，其次才是聚合站。
- 若官网要求登录才能看全部岗位，直接 `site:` 公开快照检索即可，结果标「⚠️ 需手动复核」并附再检索线索，由用户在自己已登录环境确认；详见 `references/recheck-platforms.md`。
- 海外业务招聘（如出海公司）以中国区官网为准；纯海外岗不在本 skill 范围。

## 大厂 / 头部互联网

| 公司 | 官方招聘域名 | 备注 |
|---|---|---|
| 字节跳动 | `job.toutiao.com` / `jobs.bytedance.com` | 校招 `job.toutiao.com/campus`，需登录看详情 |
| 腾讯 | `join.qq.com` / `careers.tencent.com` | 校招 `join.qq.com`，社招 `careers.tencent.com` |
| 阿里巴巴 | `talent.alibaba.com` / `campus.alibaba.com` | 含淘天、阿里云、国际站等 |
| 蚂蚁集团 | `tianchi.aliyun.com` / `job.antgroup.com` | 以官网公告为准 |
| 美团 | `zhaopin.meituan.com` | |
| 京东 | `campus.jd.com` / `zhaopin.jd.com` | |
| 拼多多 | `careers.pinduoduo.com` | |
| 百度 | `talent.baidu.com` | |
| 网易 | `hr.163.com` | 含游戏、云音乐等事业群 |
| 快手 | `zhiwen.wekan.com` / `www.kuaishou.com/about/campus` | AIGC 方向见可灵团队 |
| 小红书 | `job.xiaohongshu.com` | 社区 / 商业化 / lab |
| 滴滴 | `talent.didiglobal.com` | |
| 携程 | `campus.ctrip.com` / `job.ctrip.com` | |
| B 站 | `bilibili.jobs.feishu.cn` | 多用飞书招聘系统 |

## AI 公司 / 大模型独角兽

| 公司 | 官方招聘域名 | 方向 |
|---|---|---|
| 智谱 AI | `zhipu-ai.jobs.feishu.cn` | GLM 大模型 |
| MiniMax | `minimax-ai.jobs.feishu.cn` | 对话 / 视频 / Agent |
| 月之暗面 Kimi | `moonshot-ai.jobs.feishu.cn` | 长文本大模型 |
| 百川智能 | `baichuan-ai.jobs.feishu.cn` | 通用大模型 |
| 零一万物 | `01.ai` / 招聘公众号 | |
| 阶跃星辰 | `stepfun.jobs.feishu.cn` | |
| 深言科技 / 生数科技 Vidu | `shengshu.jobs.feishu.cn` | 视频 / 图像生成 |
| 爱诗科技 PixVerse | `pixverse.jobs.feishu.cn` | 视频生成 |
| 心识宇宙 / 心辰科技 | 官网 + 招聘公众号 | 多模态 Agent |
| 商汤科技 | `career.sensetime.com` | 计算机视觉 / 生成式 AI |
| 旷视科技 | `www.megvii.com/careers` | |
| 依图科技 | `www.yitutech.com` | |
| 智元机器人 | 招聘公众号 | 具身智能 |
| 面壁智能 | `modelbest.jobs.feishu.cn` | 端侧大模型 |

## 科技出海 / 全球化公司

| 公司 | 官方招聘域名 | 备注 |
|---|---|---|
| SHEIN | `careers.shein.com` | 跨境快时尚，技术 / 运营岗多 |
| 字节出海（TikTok / CapCut） | `jobs.bytedance.com`（切 Global） | 需登录 |
| 赤子城 / 易点天下 | 官网招聘页 | 出海营销 / 投放 |
| 蓝鲸出海相关企业 | 以各官网为准 | |

## 实习垂类 / 公共渠道（非企业官网，但稳定可用）

- 牛客网 `nowcoder.com/jobs` —— 校招 / 实习聚合，链接稳定
- 应届生求职网 `yingjiesheng.com` —— 校招公告
- 实习僧 `shixiseng.com` —— 实习为主
- 刺猬 `ciwei.com`（原刺猬实习） —— 实习 / 校招
- 高校就业网（浙大 `career.zju.edu.cn`、暨大 `job.jnu.edu.cn` 等）—— 官方、权威

## 不在本清单时的处理

遇到未在以上列表中的公司官网：

1. 先确认是「企业自有域名」（whois / 官网 footer 交叉验证），再检索。
2. 检索结果中的岗位链接，优先用 `jobstore.py` 的归一化 + 质检 subagent 验活。
3. 确认可靠后，可补充到本清单并提交（保持季度复核节奏）。
