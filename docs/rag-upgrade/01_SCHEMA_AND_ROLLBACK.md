# G1–G4 数据与接口 ADR

沿用 v2_entities / v2_revisions / v2_events，增加 knowledge_entity / evidence_edge 类型及 JSON 字段，无 DDL 删除。Claim 绑定稳定 subject_entity_ids、horse_id、source_version、passage_version、半开区间 Unicode span；每次修改保留原 Revision。

迁移脚本默认 dry-run，--apply 仅在已有项目内数据库增加实体和无歧义旧名称关联；重复执行无变化。旧 APPROVED 名称关联变动降为 DRAFT，绝不自动批准。备份副本测试迁移/重复执行；回退首选旧代码读同一 expand-only 数据，或使用完整备份副本，禁止对原库 downgrade。

KnowledgeRepository 是统一读取边界：已审证据从 V2 读，编辑图鉴从原文件/数据库兼容合并读取并进入 snapshot；创作提示不进入事实索引。EvidenceSearch 在 Passage 原文上做中文词法排序并附审核后的 Claim 关系，不把分数解释为事实置信度。每请求重新读取快照，故状态/别名/来源改动即失效，不依赖过期磁盘索引。当前适用于百条规模，后续性能门槛再决定持久倒排索引。

支持关系只来源于审核记录，不做自动 NLI 认证。未知独立性一律 UNKNOWN；文学差异不自动判定史实冲突。AnswerService 无网络调用，输出归属式摘录/BROWSE/INSUFFICIENT，SSE 为已有答案传输，不声称模型 token 流。

RAG_CORE_ENABLED=0 可回退旧聊天；旧付费生成仍额外需要 STEEDATLAS_PAID_LLM_AUTHORIZED=1，默认关闭。V2 保持旧 mode/results 字段并增添引用。引用重新校验对比准确版本、原文及状态，旧版本可以审计但不能继续用作有效事实。公开读取只允许 PUBLIC 史料；私有来源不得从搜索/版本接口泄露。
