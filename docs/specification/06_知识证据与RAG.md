# 可信历史知识、中文检索与证据审稿

## 数据结构
`HorseEntity(id,name,aliases,period,people,tags)`；`Source(id,title,edition,language,kind,rights_status,content_hash)`；`Passage(id,source_id,version,locator,text_hash,content)`；`Claim(id,revision,text,epistemic_status,evidence_strength,review_state,semantic_version)`；`ClaimEvidence(claim_revision_id,passage_revision_id,relation,span_locator)`。

**分开四类属性**：
1. Source.kind/reliability：史料/研究/文学/口传/编辑/生成，可靠性是来源属性。
2. Claim.epistemic_status：ATTESTED/LITERARY/FOLKLORE/EDITORIAL/DISPUTED/CREATIVE；属于陈述类别。
3. Claim.evidence_strength：NONE/WEAK/MODERATE/STRONG；属于引用支持程度。
4. Claim.review_state：DRAFT/APPROVED/RETIRED；属于人工治理状态。
**审批≠历史真实**。`APPROVED + DISPUTED` 是允许的组合，且在“仅历史事实”模式下不能直接采用。

## 版本与编辑
- Claim 和 Passage 版本不可变。修改产生新 Revision，建立 supersedes 映射，旧内容保留审计。
- 支持 `SUPPORTS`, `CONTRADICTS`, `MENTIONS`，不能因“引用了某段话”就默认其支持断言。
- 引用须存 page/line/paragraph 或字符 offset、原文 hash；链接打开精确摘录，不只打开某篇文章标题。
- 禁止 LLM 无审核直接写入 `APPROVED`；支持 curator 编辑草稿、审核者批准、争议历史注明依据。
- 初期选 3 个精品名马覆盖“史料强/文学强/传说强”，再建设 15–25 个精选条目；其余保持基础浏览。数字为优先级建议，不是已完成数据量承诺。

## 检索架构
- B0：保留原词频余弦实现用于对照。
- B1：中文友好 BM25，按原文结构拆段、别名索引；中文需验证分词/字符 n-gram 两种方案，不使用未经评测的默认英文 tokenizer。
- B2：按需可选多语言 embedding；仅在同义表达/跨语言评价明显受益时采用，允许 CPU 或外部 API，但均非必需。
- B3：有意义时使用 RRF hybrid；无真实收益则保持 B1 简单方案。
- 对有固定别名、朝代、人物的精确问题优先结构化过滤，避免把所有检索交给 LLM。
- 并列多条来源不得被视为独立证据：需要考虑引文转述链、内容重复和史料依赖。

## QA 模式
- A: `RETRIEVAL_ONLY`，无 LLM 时显示可检索段落/来源，绝不伪造自然语言“模型推理”。
- B: `LLM_GROUNDED`，提示模型仅基于选中 Claim+Passage 生成，保留引用 id，输出结构化答案；服务端检查每个 cited span 是否存在、版本是否有效。
- C: `INSUFFICIENT_EVIDENCE`，缺失强证据时明确标注不确定，艺术故事与历史内容分开。
- 不把一个 NLI/LLM 评审器的评分当作历史真伪结论；对重要问题提供编辑确认。

## 安全与规模
- 知识索引构建只由授权后台触发，输出路径由服务端固定、不得接受任意用户路径；原 `/ai/build` 必须审查并修复。
- 对来源文本、上传内容和检索结果进行 prompt injection 防护：资料是数据，不是命令。
- 不为了 100 条左右档案强行引入向量数据库/图数据库；先验证 SQLite/Postgres + 倒排索引。

## 最小测试
- 别名、中文无空格查询、歧义人物/年代、史实 vs 小说、冲突来源、无答案拒答、旧版引用失效、史料断言撤回、编辑审核权限；覆盖已审核精选集。
- 指标：Recall@k、MRR、Exact citation hit rate、Unsupported claim rate、Abstention precision/recall。附分母与人工标注指南。
