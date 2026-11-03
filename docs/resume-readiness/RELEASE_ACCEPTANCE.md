# 百骑谱发布候选验收（2026-11-02）

结论：**R0–R4 本地发布候选验收 PASS**。可启动、可演示、可从空库联网初始化，再离线重放；不代表生产部署或历史学准确率验收。原黑金站和业务保留。付费模型、公开部署、人工史学金标准不在本次已完成范围。

分支 `fix/resume-readiness-20261102`；[PR #1](https://github.com/rodriguezrobertbfrkx6857-sudo/baiqipu/pull/1) 的目标仍为 `feat/rag-core-major-upgrade`，不覆盖 main。应用代码测试基线 **`ff0b430ab0380b517cfcf83baaa0df1d53a06f6a`**；后续交付提交补文档、锁定依赖、复现记录和重启检查脚本。

## 提交与真实测试

| 提交 | 内容 |
|---|---|
| `9e2d366` | Top-k 反证与实体覆盖、归属摘要/拒答、快照政策、Agent 额度及异常记录 |
| `3cf84b9` | 空库初始化、固定版本重放、预检、统一启动/停止、原站测试入口参数化 |
| `0efce1a` | 许可失败不能被缓存抹掉、同名作品身份边界、原站摘要与折叠引文、真实失败演示 |
| `ff0b430` | 新环境联网取得的 revid 缓存可离线重放，兼容旧 title 缓存且仍检查固定修订 |

首先在接管的 `8e97d76` 上重跑真实应用全套测试：**88 passed**。新增边界测试先复现 **5 failed**，再修复。最终在无系统包继承的独立 Python 3.13.2 环境、260 个源码/资源文件与发布代码一致（统一 CRLF/LF 后）运行全套：**104 passed，1 条 Starlette/AnyIO 弃用警告，83.87 秒**。没有把先前 18 项隔离检查与旧 88 项相加。

主要命令：

```powershell
.venv/Scripts/python.exe -m pytest tests -q --basetemp runtime/clean-suite --junitxml reports/resume-readiness/clean-full-tests.xml
.venv/Scripts/python.exe -m pip check
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend test
npm.cmd --prefix frontend exec -- tsc --noEmit -p frontend/tsconfig.json
npm.cmd --prefix frontend run build
```

Node 22.20.0，FFmpeg 8.1.1，Windows 中文字体；3 项前端测试、类型检查、原站构建通过。完整 Windows/Python 3.13 解析依赖固定为根目录 `requirements-resume-windows-py313.lock`；其他平台尚未实测。生产级依赖安全审查不是这些测试的结论。

## R0–R4 验收表

| 阶段 | 状态 | 实际结果与证据 |
|---|---|---|
| 接管与保护 | PASS | 安全 fetch，保留唯一原始脏报告；项目内保存其副本/patch。原数据库、32 个原编译资源、脏报告哈希未变：`data-protection.json` |
| R0 应用回归 | PASS | `full-tests-initial.xml` 88 项；最终 `clean-full-tests.xml` 104 项；`full-tests.xml` 保留中途 103 项结果，勿当作最终数量 |
| R1 Top-k 边界 | PASS | 明确同命题/同实体反证优先且不超 limit；多实体不足和未完整展示反证有 metadata；未知 proposition/异实体不伪造冲突；scope/权限贯穿候选和结果 |
| R1 直接回答 | PASS | 确定性摘要、同名身份限制、完整引文折叠；出生日期/唯一归属/结局缺语义证据则拒答；历史与文学区分，无 LLM 冒充 |
| R1 Agent | PASS | 成功/超时/异常清理；失败 trace 与私有提案记录；每用户每小时 3 次、全实例 12 次采集预约，同时一轮、保守 300 秒租约；单轮请求/页数/时间预算仍在 |
| R2 预检刷新 | PASS | 默认只读，工具/字体/端口/DB/来源/许可/缓存/manifest 检查；先遇一页临时网络错误，后明确有限刷新成功；失败和成功记录均保留 |
| R2 降级边界 | PASS | 七天当前引文政策保留；保存快照独立标识非实时及最后观察；许可限制/私有化/撤回/哈希错误严格拒用，旧缓存不覆盖较新失败观察 |
| R3 干净复现 | PASS | `runtime/resume-clean` 从 git archive 开始，独立 `.venv`，空 runtime，不复制用户库；空缓存离线诚实失败；随后 9 个真实官方 API 请求取得 4 版本、6 条引文；离线 0 请求重放，前后快照相同 |
| R3 启动与重启 | PASS | 单入口固定 API 8006/原站 5178/同库 Worker；端口冲突拒绝启动；PID+创建时间核对后停止。重启后原登录 token、保存的研究 trace、知识状态均不变：`restart.json` |
| R4 原站浏览器 | PASS | 原环境和独立环境各完成桌面/手机 16 页面检查、赤兔/乌骓/的卢原输入框到精确原文、研究 trace 和文化匹配；无脚本异常/横向溢出：`browser.json`、`clean-browser.json` |
| R4 失败场景 | PASS | 真实许可文献的隔离副本验证：不存在具体日期拒答、文学不当史实、重复导入不增数、撤回后旧页 STALE/快照404：`failure-demonstrations.json` |
| R4 业务与视频 | PASS | 两环境 16 项旧业务/权限 HTTP 检查，支付沙箱；原视频工厂完成、播放206 video/mp4、可下载；两环境均完成真实 CPU 引文视频：`original-factory.json`、`source-video.json`、`clean-source-video.json` |
| R4 对外事实 | PASS | `PROJECT_BRIEF_CN.md`、`CONTRIBUTION_LEDGER.md` 区分项目与个人贡献，未虚构奖项、专家审核或独立手写经历 |

## 当前资料与实验

最终完整候选库：**100 项编辑档案；22 个已取得许可页面版本；17 个版本提供有效引文；82 条机器核对关系，覆盖 32/100 个实体；11 个作品组；人工审核 0**。82 是提及关系，不是82个独立历史事实，11个作品组也不是相互独立的事实支持。

上一份保存快照为 81 条/32 实体。本轮从空库对全部目录回放，当前候选及来源观察与旧快照并非完全相同，不能把差一条解释成准确率提升。回放曾暴露“白龙马”跨小说同名关联，已按目录身份收紧，旧候选保留但不参与有效引用。详见 `coverage.json`，不追求凑 100/100。

32 个自动关联的实体出处代理查询，Top-5 命中：字符余弦 **29/32**、BM25 **31/32**、实体约束检索 **32/32**。这是机器名称关联代理，不是独立人工金标准，不证明历史准确率100%或统计显著收益。10 个本机样例请求中位 **622.655ms**、最大 **1261.31ms**，不是生产 SLA。

真实 Research 补全 trace：空库 0 条机器引文 → 实际调用 `search_entities`、`search_evidence`、`discover_sources`、`acquire_source`、再次检索、来源比较、边检查、覆盖检查 → 1 条有效引文。共8次真实工具执行，provider 未模拟；本次 API 响应来自 **CACHE**。新环境联网记录另见 `clean-online.json` 的 FETCHED，不能把缓存 trace 称作新的网络请求。单轮/固定/自适应规则比较并非总由自适应节省调用；模型/费用均0。

## 本地演示材料

- 启动与五分钟演示：`DEMO_RUNBOOK.md`；最终保留的主工作区候选站为 `http://127.0.0.1:5178`。
- 原站截图：`reports/screenshots/resume-readiness/`；独立环境截图：`reports/screenshots/clean-release/`。
- 独立环境短录屏：`runtime/resume-rc/clean-browser.webm`；完整候选录屏：`runtime/resume-rc/browser.webm`。
- CPU 引文片：`deliverables/resume-source-quote.mp4`、`deliverables/clean-source-quote.mp4`；原工厂片：`deliverables/resume-original-factory.mp4`。
- 媒体和 runtime 留在项目本机，不上传私人数据或整个数据库。源码仓库中的原有图像仍不等于已取得公开部署/再分发授权。

## 未完成与边界

| 项目 | 状态 | 说明 |
|---|---|---|
| 68 项目录的有效文献覆盖 | INCOMPLETE | 有界采集尚未取得可用关联；不是证明文献不存在，不放宽许可/身份策略 |
| 人工史学金标准、语义蕴含、一般身份消歧 | UNVERIFIED | 引文核对与事实判断不同；规则与已知作品约束不能替代完整消歧或历史研究 |
| Dense/Hybrid、LLM/Jev 实际生成和复杂自主规划 | BLOCKED / NOT_IMPLEMENTED | 没有付费调用授权；现为检索式回答与规则工具调度，不冒充实时 LLM |
| Wikidata/HF/Kaggle 正文融合 | INCOMPLETE | 沿用既有来源限制/隔离；未把候选元数据包装成已验证事实库 |
| 公开部署、main 合并、云端 CI | NOT_EXECUTED | 本地候选通过不等于生产发布授权；只更新 PR，不覆盖主分支 |
| 其他 OS、完整前端源码恢复、赛事证明 | UNVERIFIED | 本次为 Windows 实测，保留正式编译站；原作者具体分工与奖项由本人确认 |

正常机器核对资料可使用，不等待人工逐条 APPROVED；上述边界不会人为阻塞本地产品链路。
