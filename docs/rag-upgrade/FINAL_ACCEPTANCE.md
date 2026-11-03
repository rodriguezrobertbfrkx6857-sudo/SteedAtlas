# 百骑谱统一证据核心：本轮实际验收

执行日期：2026-11-01，America/Los_Angeles。分支 `feat/rag-core-major-upgrade`。可复现代码提交 `3289ffe`；后续交付文档提交以 `git log` 为准。

本轮交付可启动的统一证据核心、原站局部引用增强和规则 Research Agent。**不是 G0–G8 全量研究/产品目标全部完成，也没有已通过专家审核的历史 QA 金标准。** 现场三条史料 Claim 都保持 DRAFT，可引用事实数为 0；真人审稿之前，真实演示会正确返回 INSUFFICIENT / BROWSE，并允许查看待核原文。测试夹具中的 APPROVED 是明确标记的合成测试资料，未导入真实知识库。

## 分阶段结果

| 阶段/验收范围 | 状态 | 实际证据与边界 |
|---|---|---|
| G0 工作区、远端同步、备份、原站基线 | PASS | 起点5359141；安全快进e30acf7；远端main=9f98765且树一致。原有视频报告未提交修改完整保留。baseline.json、49项基线测试、before截图 |
| G1 稳定名马ID、版本绑定、兼容迁移 | PASS | 100个知识实体可重复导入；无歧义旧名称关联转稳定ID。空库/副本/重复迁移/回滚测试通过；旧业务每行摘要一致 |
| G1 真实已批准精品史料 | BLOCKED | 三条候选均DRAFT，版次/权利/原文支持关系仍需真人审核；未把网页访问当人审 |
| G2 统一读取、旧API/SSE、状态真值、失效/审计 | PASS | V1 chat、ai/query、图鉴证据与V2 search共用Repository/Search；有flag回退、只读shadow比较、私有答案版本审计、引用重新核验 |
| G3 中文词法与证据检索核心 | PASS | 简繁/别名归一化；实体过滤；Passage词法检索；无Claim原文可进入待核候选；来源依赖合并，不把UNKNOWN计独立票 |
| G3 全面的时间范围、多跳及实体歧义路由 | FAIL | 尚未完成专用时间过滤/复杂图关系执行器；现有实体过滤和多实体分解不能替代这些能力 |
| G4 无模型可信问答核心 | PASS | SYNTHESIS/INTERPRETIVE/CONFLICT/INSUFFICIENT/CLARIFY/BROWSE、归属式摘录、精确span/版本校验、撤回拒用、多轮单实体指代测试；原站真实聊天→候选→原文浏览器链路通过 |
| G4 真实已审核史料上的综合历史问答质量 | BLOCKED | 缺人工批准语料与独立标签；真实库拒答行为通过，不等于历史答案质量已通过 |
| G5 真实规则Research Agent | PASS | 实际search_entities/search_evidence/compare_sources/inspect_claim_edges/check_coverage调用，get_passage_revision实测trace；硬调用/时间/轮数上限；私有提案、一次性人工接受/拒绝记录。不能自动批准事实 |
| G5 LLM/Jev/自适应质量收益 | BLOCKED | 外部模式409拒绝；零模型调用、零费用。策略的实际调用数不同，未声称公平质量收益 |
| G6 候选集、重跑实验、负结果 | PASS | 40道复杂候选、150组claim-span候选、104题名称诊断、逐题日志、bootstrap区间；未伪造gold/κ |
| G6 双人标注与复杂QA准确率 | BLOCKED | 标注者0、gold0；无法计算可信的支持率/漏冲突率/过度拒答率/人工分钟数 |
| G6 扩展120题与完整学术差异复核 | FAIL | 本轮完成40题；新研究材料未齐，完整文献复核与120题扩展未完成 |
| G7 原黑金UI保护与引用增强 | PASS | 49个原资源审计，仅index.html增加1行script；编译JS/CSS/字体/图片未改。8页面×桌面/手机，前后各16张截图，无pageerror；稳定首页像素差异0 |
| G8 下游CPU、证据依赖、旧业务冒烟 | PASS | 统一EvidenceBundle进入创作工程；撤回触发NEEDS_REVIEW；真实MP4+SRT、私有媒体、DAG原测试保留；16项业务HTTP检查通过 |
| G8 完整生产安全与全部交互验收 | BLOCKED | 未部署生产、未跑外部服务。页面加载与HTTP冒烟不等于每个管理/商城UI动作均验收；历史支付仍为内存沙箱，未做全面支付安全改造 |

## 本轮测试与运行

- 后端最终：**62 passed，0 failures，0 errors**。`reports/rag-upgrade/final-tests.xml`；pytest墙钟128.16秒，XML testsuite累计126.374秒。
- 前端：**3 passed**；TypeScript exit=0；原站打包exit=0。见 frontend-tests.txt、frontend-checks.json。
- 核心测试覆盖：精确版本/span、HTML转义、防私有来源泄露、审核权限、错误span、来源撤回、编辑版本变化、旧索引内容/metadata更新、旧API/SSE、文学与历史、同源票数、未知来源独立性、无答案、代词澄清、实体关联、Agent越权/预算/重复审查、旧答案过期、创作依赖。
- 数据验证：SQLite online backup；新建副本执行 upgrade→upgrade→downgrade→upgrade；旧业务行摘要相等；知识导入第二次actions=[]。原库最终表计数不变，原有未提交报告SHA不变。
- 原站业务：注册、登录、me、名马列表、图鉴库、签到、抽卡、两套收藏读取、商品、下单、订单读取、沙箱支付创建/成功、匿名项目/研究拒绝。只作用于隔离副本的测试账户，没有实际付款或配送。
- 浏览器：原chat输入框实际发起POST /api/v1/chat；打开claim-1@2原文高亮；显示STALE/待审；登录后实际规则研究并呈现工具轨迹。见 ui-flow.json。
- CPU：原视频工厂点击运行，完成100%，预览206 video/mp4，下载可用，无pageerror。导出720×1280、H.264、24fps、24秒、841269字节，SRT三条。视频是程序模板与场景字幕，无TTS/生成模型。见video-factory.json、delivery-evidence.json。

## 对照实验

以下仅为**名称诊断**，数据从旧corpus派生，不能解释成历史QA正确率。n=104，bootstrap=1000次，固定seed=20261101。

| 方案 | MRR | 95% bootstrap CI | Recall@5 | nDCG@5 |
|---|---:|---|---:|---:|
| V1词频余弦 | 0.9554 | [0.9193,0.9856] | 0.9808 | 0.9605 |
| 归一化BM25诊断 | 0.9728 | [0.9455,0.9952] | 1.0000 | 0.9797 |
| 稀疏RRF | 0.9578 | [0.9241,0.9866] | 0.9904 | 0.9653 |

稀疏RRF没有超过BM25，**不升级为默认**。这不是Dense/Hybrid实验，也不是实际三条Passage上的检索gold评测。40道复杂题实际跑过真实库，全部结果保留answers-raw.json；因为没有gold，相关准确率记BLOCKED。BM25延迟比已缓存词频向量高，原始p50/p95在evaluation.json；计时为离线诊断路径，不是端到端聊天SLA。

Agent single/fixed/adaptive实际运行，日志保留每次工具输入、输出与哈希。single只搜索1次，fixed/adaptive搜索3次；相同上限不是相同实际调用预算，因此没有报告策略质量提升。真实库无APPROVED证据，所有策略都如实指出缺口。另有真实get_passage_revision读取记录，未模拟LLM。

## 架构与残留工作

1. 所有知识读取在当前事务中重建快照；不使用生成答案缓存。已保存答案采用保守快照过期标记，尚未优化为按依赖最小范围失效。旧版本仍在Revision中。
2. Horse稳定ID已落地；其他实体类型有策展接口，尚无完整人工策展的Person/Event/Work/Location关系图。EvidenceEdge目前主要由Claim的关系/版本字段表达，独立多边治理工作台未完成。
3. Research当前是确定性计划、检索、比较与ReviewFinding提案；接受只记录审查结果，不自动提交APPROVED Claim。完整ClaimDraft编辑管理界面仍需补充。
4. 原站完整React源码仍缺失；本轮只新增scoped Shadow DOM适配器。独立/旧管理页面不等于已有完整知识管理UI。原站静态“OpenAI可用时模型”说明未批量改写，新增区域明确显示本地模式。
5. 本轮已验证原文链接，但不能代替古籍版本与权利审稿。乌骓原ctext链接返回403，记录了可核对的维基文库替代版本，未自动替换已存资料。
6. 没有完整生产安全认证；测试覆盖不能证明不存在全部漏洞。旧支付为历史内存沙箱；应在任何公开部署前单独完成交易/权限审计。
7. 本轮未调用付费API、Jev、外部生成、发布服务或GitHub推送。未修改运行原库，展示站使用已迁移副本。

## 提交

- `2f10ef0` G0接管与保护
- `5c822cc` G1–G3统一版本证据和检索
- `e576597` G4–G5旧聊天接线及Research工具
- `5799169` G6候选与对照实验
- `d002d8f` G7原站局部增强与视觉回归
- `3289ffe` G8下游证据、答案审计与本地交付

文件清单见 reports/rag-upgrade/changed-files.txt。报告是本轮本地验收，不代替生产验收。
