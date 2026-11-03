# SteedAtlas / 百骑谱 — 可信 RAG 核心与全站智能能力大升级执行总纲

> **状态：待本地工程 AI 执行。此文件是任务计划，不代表功能已开发完成。**  
> 起草日期：2026-11-02（项目接管计划）  
> 源码参考：GitHub 私有仓库 rodriguezrobertbfrkx6857-sudo/baiqipu，审查起点 5359141b331dcdeb5475a9b6a3a923f207617355（2026-11-01）；实施前必须重新核对实际 HEAD 和本地未提交文件。  
> 研究输入：2026-11-01 的 SteedAtlas 独立学术研究四份报告（文献综述、架构比较、实验设计、主报告）。这些报告是概念与文献研究，**没有真实运行本仓库实验**，不可将其推断记为已验收。  
> 执行语言：中文；代码、API 与论文术语可使用英文。外部学术研究材料如有特殊约定，可单独使用英文。  
> **最高视觉约束：默认原站黑金风格，绝不以非默认浅色 React 草稿取代；不得整站重做。**

## 0. 任务定义、边界与成果目标

百骑谱不是以视频工厂为中心的项目。其基础价值是历史名马知识资产、可核验的历史与文学证据、可用的文化问答，以及基于同一可信知识系统的 Research Agent、内容创作和已有商业互动。

**本轮是实质性的大升级，不是仅写研究文档或只补一个检索函数。** 优先完成统一知识平台、可信 RAG 的真实后端闭环、原站聊天与图鉴的前端集成、知识治理管理链路、评测和跨模块回归。Research Agent 做出真实工具调用/提案/审查的可用核心；Hybrid / Jev / 多 Agent 属于门槛式可选实验，不能为堆技术牺牲基线质量。当前已验证的 CPU 视频/DAG 保持稳定并改为消费统一证据，不继续以视频工厂为开发主线。

功能优先序：知识库与 RAG 约 60%，可信问答与 Research Agent 约 20%，原站知识交互约 10%，视频工厂知识接线及全站回归约 10%。这是**研发资源建议**，非完成率或验收权重。安全、可复现和测试贯穿全程。

不可触碰的边界：
- 保留原站黑金视觉：色彩、首页、顶部导航、图库/图鉴、字体、Logo、背景、交互与既有页面入口。见 docs/UI_CHANGE_POLICY.md；新增引用/证据对比组件须局部同风格嵌入。禁止将 frontend/src/main.tsx 浅色草稿作为默认界面。
- 保留账户、抽卡收藏、图鉴、测验、商城、支付沙箱、管理功能、现有视频工厂及已经实测的 V2 后端/FFmpeg/DAG；不偷换、不删除、不重建用户数据库。
- 不能未经批准执行不可逆删除、生产部署、公开仓库/媒体、付费模型调用、导出私密数据或越界操作。Git 不得 force-push/reset --hard/clean 未备份内容。
- 开发者所用 AI 订阅档次**不代表**自动拥有 API 额度或任何第三方服务的付费授权。未配置模型时必须真实可用 RETRIEVAL_ONLY / BROWSE 模式，外部能力标为 BLOCKED，而非 MOCK 假成功。

## 1. 已知仓库事实与必须重新核验的缺口

以下是 5359141 起点的**静态代码观察及历史报告**，不是今天的本地运行验收。请以实际分支、文件和测试重新核验，差异写入审计报告。

- 原后端在 wangzhan/{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server/。app/services/ai_engine.py 使用 data/corpus.json、data/vectordb.json，所谓 embedding 实际是词项频次 Counter；ensure_vectordb 仅在索引文件不存在时构建，存在内容更新后索引过期的风险。V1 app/routers/chat.py 使用这个检索与可选 LLM/规则回退，并混入性格/商品推荐；返回的来源可由综合故事摘要回退，并非自动满足精确历史引用。其 SSE 是先合成回答再逐字符送出，不等于真实模型增量生成。
- V2 app/v2/api.py 的 GET /api/v2/search 主要从 APPROVED + SUPPORTS Claim 按 BM25 返回结果；尚不是完整证据约束的生成式问答，且不直接索引原始 Passage。app/v2/domain.py 有基本中文 n-gram/别名 BM25，缺少规范化实体连接、跨来源支持关系检索与综合证据包。
- app/v2/contracts.py 的 ClaimInput 没有稳定的 horse_id / subject_entity_ids；/api/v2/horses/{horse_id} 通过 c.data.get("horse_name") 与展示名匹配，而 new_claim 直接保存 ClaimInput，存在实体关联丢失风险。必须先用真实数据和测试复现，再进行兼容迁移。
- 旧 100 条 corpus、名马介绍、视频创意文本（如 data/video_factory_rag.json）与精确史料不能混为一类。文学与历史混合叙述只能先标为 EDITORIAL/待核验，绝不自动转成已证实 ATTESTED。
- V2 已实现通用 Entity / Revision / Event、部分 Source / Passage / Claim 审核、项目/任务/DAG/媒体。对其做 expand-only 演进，**不要盲目另建相同的六张表并抛弃既有模型**。
- app/v2/agent_providers.py 当前运行模式是 MANUAL、RULE_BASED；LIVE_LLM 只保留被阻塞骨架，不存在真实 LLM Research Agent。旧视频工厂已通过 app/v2/compat.py 接 CPU 后端，需保留。
- reports/RESEARCH_FINDINGS.md 的 B0/B1 MRR 0.9554/0.9728 来自约 104 条以名称为主的检索题，不能当成复杂历史问答或引用准确率。报告记载 49 项 Python 与 3 项前端本地测试通过，但尚未见云端 CI 验证；本轮必须亲自重跑。
- GitHub 内容是源码，不包含实际运行数据库、用户数据、成片与私密密钥。请先探测本机真实运行数据，再考虑导入和迁移。

## 2. 推荐技术主干与明确不做的事

采用 **Architecture L：Evidence-Grounded RAG** 作为本轮必达工程基线：

原站页面/聊天/图鉴 -> Legacy API Compatibility Adapter -> KnowledgeRepository (稳定 ID + 版本 + 审核) -> EvidenceSearch (实体/别名 + 优化 BM25 + 结构化关系 + 来源/状态筛选) -> EvidenceBundle (Source/Passage/Claim/Edge/引用片段/来源依赖) -> EvidenceValidator -> AnswerService (BROWSE / SYNTHESIS / INTERPRETIVE / CONFLICT / INSUFFICIENT / CLARIFY) -> 原站统一呈现。

**先达到端到端可用，再实验升级**：
- Architecture H：可选 Dense/Hybrid/RRF/Reranker，仅当独立测试集对比强 R0 有实质净收益且不损害引用支持率时才进入默认。
- Architecture A：受预算约束的 Research Agent；真实工具调用、证据集合增量、追踪与审批需实现，并与强固定分解/单 Agent 工具链公平比较。多 Agent 不作为必选架构。
- Jev / TypeSafe：仅做可插拔候选决策器的接口与评测计划。与 J0 规则、J1 轻量分类器、J2 通用 LLM、J4 不路由作公平对照；没有实际凭据、费用授权、隐私评估和域内校准时不接生产。
- 不强行引入 Qdrant、Milvus、Neo4j、LangGraph/CrewAI/AutoGen 的整套基础设施；证明现有数据库/倒排索引无法满足需求后，才审慎引入。

## 3. 分阶段执行：必须继续开发、提交证据，不得以讨论替代实现

### G0. 接管审计与不可逆保护（先做，必须 PASS）

1. 在本地 Git 仓库确认路径、权限、分支、HEAD、未提交修改、被忽略运行数据；从 GitHub 拉取本计划前先检查冲突，**不得覆盖他人进行中的代码**。
2. 建立专用开发分支 feat/rag-core-major-upgrade 或沿用已存在的 feature 分支，保护重要工作树改动。对 DB/索引/用户媒体/配置留存校验哈希与脱敏备份清单；不要把备份加入 Git。
3. 重新运行后端、前端、旧站/视频工厂、数据库迁移及原版浏览器回归。标记 PASS/FAIL/BLOCKED，绝不可复用旧报告冒充本轮 PASS。
4. 输出 docs/rag-upgrade/00_BASELINE_AUDIT.md、reports/rag-upgrade/baseline.json、当前黑金首页/问答/图鉴/视频工厂截图、旧接口响应快照。
5. 对照现有 README、docs/RUNBOOK.md、docs/FINAL_ACCEPTANCE_A0_A12.md、docs/UI_CHANGE_POLICY.md；明确可复用代码和本轮禁止触碰的文件。

### G1. 统一可信知识模型与可逆迁移（P0，必须 PASS）

1. 数据盘点：盘点 100 条 corpus、独立名马 JSON、数据库 Horse、已有 V2 Source/Passage/Claim/Revision、所有“RAG”相关文本；输出总数、可检索/可引用/已审核/纯编辑/创作材料的分布与缺口。
2. 设计稳定 Entity ID 与 alias：Horse、Person、Event、Work、Location 的必要实体关系（按实际数据谨慎增补）；修复 /horses/{id} 的 Claim 关联 bug，避免按展示名称做唯一主键。建立多实体引用的兼容迁移与双向索引。
3. 在现有 V2 数据模型上 expand-only 增加缺失的 EvidenceEdge（SUPPORTS/CONTRADICTS/MENTIONS/INDETERMINATE）、来源体裁/版本/原文定位/哈希、来源间 derived_from / independence_group、审稿事件与状态。严格区分文献体裁、历史断言性质、审稿状态、证据支持强度。
4. 旧 corpus 和人物故事导入为 EDITORIAL / 未核验资料；视频工厂的脚本/镜头/提示词进入独立 CREATIVE 索引。没有可追溯来源的材料不得自动晋升为历史事实。
5. 先以赤兔、乌骓、的卢建立**真实可定位**的精品证据样例。没有能核查的原文、来源版本和使用权时保留 DRAFT / PENDING，不伪造引文、页码或人工审核。可先构建待人工核对的候选工作台；其他名马保持原展示可用。
6. 新旧数据对照：迁移前后旧表数据条数、ID、用户记录、商品/抽卡/媒体不变；空库迁移、备份副本迁移、重复迁移、回滚演练必须可重复且不动原库。
7. 产物：schema ADR、迁移说明、source coverage audit、实体关联和不可变引用测试。

### G2. 一个知识权威、一个检索核心（P0，必须 PASS）

1. 建立统一模块边界：KnowledgeRepository、EvidenceSearch、EvidenceValidator、AnswerService、ResearchPolicy，接口携带 corpus_snapshot_id、实体/证据 revision、权限范围及状态标签。避免再出现各 API 内独立检索/缓存逻辑。
2. V1 /api/v1/chat、/api/v1/ai/query、/api/v1/horses/rag-library 与 V2 /api/v2/search、/api/v2/horses 使用同一知识服务；保持旧请求结构、旧关键响应字段、SSE 兼容，增加可选 evidence/citations/mode/review_status 字段。商城推荐与情绪标签属于可选互动模块，不得作为历史事实证据。
3. 先提供只读 shadow compare：同一合规问答用 V1 与 V2 路径比较，固定数据快照、日志脱敏、差异分类。使用 feature flag 小步切换/回退，不删除 V1。
4. 修复索引陈旧性：新增/更新/撤回 Source、Passage、Claim 和 alias 时，事务内或可信事件流触发索引增量更新/失效；变更 review_state 即使文本哈希没变也必须失效。GET rag-status 区分 SOURCE_PRESENT、INDEX_READY、EVIDENCE_VERIFIED、LLM_AVAILABLE，不能只因有旧向量文件就宣称历史问答“ready”。
5. 明确回答缓存 provenance digest：引用 (claim_id, revision, passage_id, revision, review_state, genre, index_snapshot_id)；修订触发精准失效，旧回答可审计但标 stale。
6. 产物：接口合同/回滚 ADR、旧接口快照兼容测试、数据一致性与失效测试。

### G3. 中文检索与证据检索（P0，必须 PASS）

1. 固定强 R0：规范化中文简繁、异体字、名马别名、跨作品人物同名与歧义、时间范围/事件匹配；BM25 在真实 Passage 上运行，优先按篇章/段落切分并支持原文 locator，避免简单“全文名马故事”自证。
2. 根据问题类型选择：直接实体查找、结构化关系查找、跨来源/多实体并行检索、普通词法检索；初期可用确定性路由，未知时保守检索与解释。
3. EvidenceBundle 对每条命中返回可点击的 source_id、passage_id@revision、span、claim_id@revision、relation、genre、review_state、independence_group 和检索分数；分数仅是相关性，不是事实置信度。
4. 面对相互矛盾文献需正确区分“同一事实性主张的冲突”和“文学演绎与史籍记载不同”；对同源转载不能伪计独立支持票数。对没有已批准精确证据的实体，允许 BROWSE 编辑资料并明确标记。
5. 将 R0 作为可复现强基线，保留现有旧检索便于真实对照；只有实测存在概念性改写召回不足时才考虑 Dense + RRF/重排。
6. 产物：索引构建/修复脚本、证据检索 API、可解释排序日志、测试数据及多类别检索评测。

### G4. 真正可核验的历史文化问答（P0，必须 PASS）

1. 分离三种知识用途：史料考据、文学文化探索、创作/文化推荐。前两者的事实断言必须绑定有效引用；创作内容不得悄悄回流事实索引。
2. 构建 AnswerEnvelope：BROWSE、SYNTHESIS、INTERPRETIVE、CONFLICT、INSUFFICIENT、CLARIFY；每个 atomic claim 包含可解析的 evidence 列表，注明证据类型、适用范围、冲突或不充分原因。
3. 无 LLM 时，提供**真实的证据浏览、比较来源、确定性摘要或明确不生成**的可用体验；不得把模板输出声称模型结果。可配置的实际 LLM Provider 仅在用户已明确授权且环境有可用凭据时调用；记录 model/version/tokens/费用/调用 trace，禁止将密钥回传前端。
4. 生成后执行确定性的引用 ID/版本/span/来源权利验证，并对陈述与证据的 SUPPORTS/MENTIONS/CONTRADICTS 关系使用已审稿边；自动 NLI/模型审查只能作为待验证警告，不能代替历史真伪证明。
5. “本库未发现资料”不同于“历史上不存在”；CONFLICT 不能偷换成单一答案；正确拒答与过度拒答均需衡量。文献仅支持“某书记载”时必须用归属式表述。
6. 在原站聊天、名马详情中呈现精确来源卡片/版本/文体/争议标签与原文定位，仅局部黑金风格增量改动；无需推倒整个编译前端。
7. 端到端真实验收：名马关联、跨书对照、人物关系、文学/历史、同源转载、撤回版本、无答案、多轮代词追问；查看引用具体位置，不接受只打印“有引用”。
8. 产物：真实 chat → evidence → answer → clickable citation 浏览器视频/截图或测试凭据、接口事件、案例与回归。

### G5. Research Agent 的真实工具化升级（P1，必须完成可用核心）

1. 单 Research Agent + Read-only Tools 优先：search_entities、search_evidence、get_passage_revision、compare_sources、inspect_claim_edges、check_coverage、check_project_evidence。记录每次检索的真实输入/输出摘要和状态。
2. 采用 Proposal → Validation → Human Review → Commit；Research Agent 只能提出待审的 EvidenceBundle/ClaimDraft/ReviewFinding，不得直接将 Claim 改为 APPROVED，不得擅自发布、购买、删除或写数据库历史事实。
3. 查询分解、证据缺口检测、补检索、冲突比较和停止条件设硬上限（轮数、令牌、时长、调用数）；简单问题走普通 RAG，复杂问题再升级。若无 LLM Provider，保留可用确定性工具链并明确 RULE_BASED。
4. 设计强对照：单次 RAG vs 固定分解/单 Agent Tools vs 自适应 Agent，在相同实际检索次数、模型、token、证据上限下测质量；不要以多调用换“提分”。
5. Jev 只实现可拔插的 interface、运行时标识和 J0 规则基线；Jev LIVE API 不得默认打开。无资金授权时 J3 标 BLOCKED；预先设计中文/异体/跨语领域漂移和 ECE 校准，不能用 vendor score 当史实置信度。
6. 产物：Agent trace、工具权限测试、提案审批回归、成本预算限制、无模型模式的真实演示。

### G6. 真实数据、评测与科研可信性（P0/P1，必须推进）

1. 引入自动化评测框架，区分“旧名称检索诊断集”与“复杂历史问答评测集”；旧 n=104 的 MRR 不能作为新产品准确率。
2. 先构造 40 个专家待核问题及约 150 个 claim–span 判断候选，制定双人独立标注与第三方仲裁规则；**若没有两位真实标注者，不得伪造 κ、金标准、已核验题数**。把自动候选和人工 gold 分别存储。
3. 逐步扩展约 120 道分层问题，覆盖精确实体、别名、关系、多跳、改写、时间范围、史籍与文学差异、真冲突、来源依赖、无答案、追问与撤回证据。禁止全部题目直接从文本名称字段生成“gold”。
4. 指标须同时报告 Recall@k / nDCG / MRR、citation span validity、supported-claim precision、unsupported-claim rate、missed-conflict rate、false-corroboration、abstention/over-abstention、p50/p95、token/费用及人工审稿分钟数；分母、样本量、原始结果、置信区间明确。不能用单一 LLM judge 的未经验证输出冒充人工金标。
5. 按 Architecture L → H → A 与 J0/J1/J2/J3/J4 单因素消融进行预注册对照；如 Jev 或 Hybrid 没有超越强基线，明确 no-go，不将性能假设写为已证实科研创新。
6. 复核与现有 AIS/ALCE/ConfRAG/EVIRAG/Adaptive-RAG/来源依赖研究的差异，不对已有 Source–Passage–Claim、向量检索、Agent 框架或版本失效机制主张原创算法。
7. 产物：评测数据说明、标注规范、基线脚本、可重跑日志、表格、负结果、统计限制，以及研究可行性结论。若人类标注缺失，要交付完整候选题和明确 BLOCKED 的验收。

### G7. 原站黑金 UI 完整保护和知识增强（P0，必须 PASS）

1. 从 docs/UI_CHANGE_POLICY.md 提取冻结标准。默认入口和构建继续指向原黑金界面，浅色草稿不进入默认发布。
2. 仅新增知识引用/来源对照/历史与文学标签/问答状态/检索提示和适量管理入口，样式复用现有组件；严禁更换首页、导航、主要字体、图片和背景。原编译 React 源码缺失时优先通过现有页面接口、局部脚本与 scoped adapter 实现，不做脆弱的批量 minified JS 取代。
3. 对图鉴、问答、注册登录、抽卡收藏、商城沙箱、测验、视频工厂做 E2E 回归。回答必须在 UI 中可查到原文来源；没有权限时安全显示不可见，不泄漏私有用户数据。
4. 以真实旧站截图作基线，对桌面和移动端做视觉对比；不存在大面积风格漂移、导航失效、严重布局溢出。注意无障碍/加载/错误态，但不为此重做整个前端。
5. 产物：旧站 vs 当前截图、差异说明、浏览器脚本、真实交互结果。

### G8. 下游视频工厂与最终整体验收（P1，必须 PASS/明确 BLOCKED）

1. 视频工厂、创作 Agent 通过同一 EvidenceBundle 获取经过标注的名马知识，保留脚本、镜头等 CREATIVE 资料的独立索引，不把视频提示词当史料。
2. 当引用版本撤回，相关成片脚本/创作工程进入 REVIEW_REQUIRED 或 STALE，不删除既有用户作品；只有明确用户授权和真实检查后才重生成/更新。
3. 旧 V2 compat/CPU DAG/FFmpeg/MP4/SRT、租约重试、视频私有 ACL 与签名票据必须保持可用。修正已知风险：兼容层模拟状态/提供商能力不可误导；自动任务创建不应伪造历史事实的人审批准；Worker connected 不应仅为固定布尔值。
4. 安全：认证/越权、索引注入/Prompt Injection、文本导入、路径穿越、第三方数据发送、素材权利、密钥和运行数据库进 Git、报告含敏感信息、恶意引文和模型工具越权的测试。
5. 全栈验收：Python/Node/TypeScript、空库与已有库迁移、原站全功能、V1/V2 API contract、实际 citations、问答无模型/有模型（仅已授权环境）、Research Agent trace、视频 CPU 出片与下载、浏览器 desktop/mobile。
6. 产物：docs/rag-upgrade/FINAL_ACCEPTANCE.md（PASS/FAIL/BLOCKED）、docs/rag-upgrade/FINAL_DELIVERY.md、reports/rag-upgrade/* 机器证据、变更风险/回滚指南；附复现命令与 Git commit SHAs。所有 PASS 必须是本轮真实执行结果。

## 4. 决策与验收门槛（反对“伪完成”）

| 门槛 | 必须满足的可查证结果 |
| --- | --- |
| D0 原站与数据保护 | 原黑金入口、样式与旧功能无大回归；迁移对原业务数据不减少；安全备份证明 |
| D1 知识权威一致 | 旧聊天与 V2 可从同一证据索引取数；旧 API/SSE 客户端合同测试通过；来源和创意索引隔离 |
| D2 关系与溯源 | Entity ID 稳定；Claim 与名马/人物关系可正确显示；精确 Source/Passage revision/span 可打开；无无来源“APPROVED” |
| D3 可信问答 | 史料/文学/创意分层；至少 8 类真实场景测试；对冲突与无证据正确返回 mode；每个事实性引文可确定性验证 |
| D4 更新失效 | 修改、撤回、审核状态切换能使引用/缓存/依赖项目更新审查状态，并可回放版本 |
| D5 Research Agent | 至少一条已运行真实工具链与待审提案 trace；无 LIVE Provider 时只显示实际 RULE_BASED/MANUAL |
| D6 检索/研究评测 | 强 R0 与 V1 及可选 H/A 对照分离记录；gold 未人工确认的指标绝不宣称金标；已有 MRR 不被冒充新能力 |
| D7 全站回归 | 账户、图鉴、问答、抽卡/收藏、商城沙箱、视频工厂、权限和 CPU 出片未退化 |
| D8 研究与付费边界 | Jev/付费 LLM/云服务仅在授权配置下真实运行；没有授权记 BLOCKED，绝不能假造外部模型结果 |

验收结果每项只允许 PASS / FAIL / BLOCKED，写明所执行命令、数据快照、日志路径、测试分母和截图；不可把“代码文件存在”“先前报告说 PASS”写成当次通过。

## 5. 工程操作方式（交给本地 AI）

- 从当前工作树与 Git HEAD 开始，不从零复刻 V2；先修最关键基础，按 G0→G8 提交**有内容的增量代码**。如某阶段过大，拆成最小可合并的独立切片，但本次会话在授权范围内应持续推进，不能只写规划就停止。
- 每阶段完成：实现 → 真实测试 → 消除失败或标明阻塞 → 确定性证据 → 单独 commit → 下一阶段；优先工程落实，不必阶段阶段征求同意。不得在测试失败时写“全部完成”。
- 不要引入伪模型、伪引用、伪评测、伪 Gold、伪视频；明确已完成/未完成/实验性。对缺少独立专家标注与外部授权的问题可提供可执行工件并标 BLOCKED，继续完成其他允许的任务。
- 每次开始改动前，先比对当前 git status；使用定向 git add，不把密钥、运行 DB、生成媒体、个人日志、档案附件上推到 GitHub。文档/脚本应可重现，避免只存在本地未追踪文件。
- 优先保留兼容；如必须变更原站三行以外文件，应列出用户可观察影响和视觉回归截图。遇到会影响用户数据/线上系统/不可逆删除的操作必须单独获批。
- 在末尾生成一份**真实的交付摘要**，逐项汇报 G0–G8、当前 SHA、文件变更列表、测试证明、用户可见功能、阻塞项、下一步优化建议。不得承诺后台继续工作。

## 6. 必读地图（本地 AI 在仓库里读，不需向用户重新索要 ZIP）

- 当前现场文档：README.md；docs/CURRENT_REVIEW_2026-11-01.md；docs/UI_CHANGE_POLICY.md；docs/RUNBOOK.md；docs/LEGACY_V2_INTEGRATION.md；docs/AGENT_MODE_TRUTH.md；docs/FINAL_ACCEPTANCE_A0_A12.md；reports/RESEARCH_FINDINGS.md。
- 历史 RAG：server/app/services/ai_engine.py；server/app/routers/chat.py；server/app/routers/ai.py；server/app/routers/horses.py；server/data/corpus.json；server/data/video_factory_rag.json（需本地确认此路径）。
- V2 数据和运行时：server/app/v2/api.py、domain.py、models.py、contracts.py、agent_providers.py、compat.py、runtime.py、media.py、security.py；Alembic revisions；tests/；experiments/run_benchmarks.py。
- 原站：wangzhan/baiqipu.com-source-20260424-194149/；wangzhan/video-factory-workflow/；wangzhan/rag-proof-showcase/；frontend/package.json、vite.config.ts；scripts/browser_qa_original_v2.py、scripts/compat_e2e.py、scripts/package_delivery.py。
- 科研依据：独立 Claude 报告主张**先做强 Architecture L，H/A/Jev 作为须验证候选**；先建立真实证据覆盖和标注。参考 AIS (Computational Linguistics 2023)、ALCE (EMNLP 2023)、BEIR、ConfRAG (ACL 2026)、EVIRAG (EMNLP 2026)、Adaptive-RAG (NAACL 2024)。请重新核实文献内容和新工作，不要从标题推断创新成立。

## 7. 第一次可运行的用户演示（不得缺席）

最小端到端演示应从原黑金网站出发：

1. 在图鉴选赤兔/乌骓/的卢之一，进入名马知识页，看到编辑整理与已核验证据的区别。
2. 在原站 AI 聊天问一个跨史籍/文学的问题，系统定位可追溯的 passage 与版本；必要时返回 CONFLICT / INSUFFICIENT，而非编造结论。
3. 点击原文引用可核对 source、具体段落与审核状态；在后台修改或撤回一条 claim 后，旧答案缓存标 stale，不再当有效引用。
4. 询问多实体对比问题，能看到真正调用搜索工具和受限 Research Agent 的审查提案（无真实 LLM 时准确标 RULE_BASED）。
5. 原站既有抽卡/收藏、商城沙箱和 CPU 视频工厂照常可用；从同一知识 API 生成受证据约束的创作素材，用户创意与历史证据保持分离。
6. 用运行日志、截图、pytest/E2E 结果和数据快照证明上面所有状态，而非录屏或文档中的自述。

**完成定义：不是“所有高级模型都接好了”，而是一个可以真实使用、知识可核验、旧站无损、研发成果可复现的重大版本升级。**
