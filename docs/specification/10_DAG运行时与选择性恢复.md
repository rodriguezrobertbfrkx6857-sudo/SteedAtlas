# 双层 DAG、持久化执行与证据感知局部恢复

## 一、两张图
1. **ContentGraph**：Source/Passage/ClaimRevision → ScriptRevision → ScenePlan/SceneBibleRevision → MediaAsset/TimelineRevision → FinalArtifact。维护来自内容语义的影响关系。
2. **ExecutionGraph**：Job → TaskNode → Attempt → Artifact；记录输入 hash、依赖 node、工具版本、状态、恢复策略。由 `WorkflowCompiler` 根据权威创作数据生成，执行图不可接受任意无校验前端 JSON。

## DAG 编译器
- 节点 ID 唯一且输出 schema 可解析；所有依赖存在；必须无环；限制节点总量/并发/深度。
- 拒绝 `unknown kind`、未授权 external tool、超限 ffmpeg filter、恶意 shell 参数。
- 先编译计划和预估资源，显示计划差异与审批要求，再入队执行。
- 新旧工作流的 `nodes`/`connections` 经适配器归一化；旧固定阶段可作为兼容性 baseline，但不能再是唯一执行方式。

## 任务状态机
`DRAFT → READY → LEASED → RUNNING → VERIFYING → SUCCEEDED`；失败为 `FAILED_RETRYABLE → READY`、`FAILED_FINAL`、`INVALID_OUTPUT`；控制态 `AWAITING_APPROVAL`, `CANCEL_REQUESTED`, `CANCELLED`, `STALE`, `NEEDS_REVIEW`, `UNKNOWN_OUTCOME`。
- RUNNING 输出必须经过校验、记录 hash 后才能变为 SUCCEEDED。
- 状态转换需要 DB 事务/CAS；Worker lease 包含递增 `fencing_token`，防止老 Worker 在新 Worker 后提交。
- 原子写任务状态和通知 Outbox 事件，用户界面只依赖真实持久状态，不通过内存列表推断成功。
- Worker 重启自动扫描过期 lease、恢复确定可重试任务；外部任务结果未知不得盲目重复提交。
- 取消只保证本系统不继续发布/写入新工作流结果；对于无法取消的外部 API 结果按规则保留审计。

## 指纹（不依赖模型训练）
`fp = SHA256(node_kind, schema_version, normalized_params, tool_version, input_asset_hashes, claim_revision_ids, scene_bible_revision_id, approved_policy_version, render_preset_version)`。
- 对纯确定性步骤（字幕/图片缩放/FFmpeg）可严格按指纹复用验证过的结果。
- 对 LLM 提案之类非确定性步骤，缓存策略单独记录 `seed`, `model`, `prompt_template`, `creative_intent`; 已审稿结果不应因随机值碰巧相同而替换。
- 读缓存时要检查存储物是否存在、SHA/解码校验通过、版权与事实标签仍适用。

## 保守影响分析：三值结果
- `REUSE_ALLOWED`：依赖完整，哈希/所有涉及知识版本/状态未改变，且产物仍合法。
- `REBUILD_REQUIRED`：已知受影响且可确定重编译方式（字幕、视频组合、风格参数等）。
- `REVIEW_REQUIRED`：历史语义变更或依赖不完备，不能证明安全复用；提醒审核后再决定。
- 底层变更传播需要标注 `direct_dependency`、`derived_dependency`、`uncertain_semantic_dependency`；不得把“没显式 CITES”当作永远无影响。

## 修订与缓存一致性
- 新 ClaimRevision 不意味着旧 Claim 永久错误，但所有受它影响的产物需重新检查当前使用政策。
- 不要误把 `review_state=APPROVED` 与 `epistemic_status=ATTESTED` 当作同一属性；`DISPUTED` 也可能被编辑批准为“有争议叙述”。
- 如果更新文本同时修改角色关系、故事时间线或全局 Scene Bible，相关 Scene 需要保守的复核/重建。
- 某个场景 TTS 变化，字幕对齐和合成需要重建，但其他无关场景原始素材应保留。

## POC 与运行时选型门禁
DB-backed worker 与成熟框架都至少通过：并发抢租、提交瞬间崩溃、旧租约回写、数据库重启、重复回调、用户取消、文件消失、历史版本冲突、工作流复制、错误任务重跑、无 API 配置纯 CPU 导出。
**不能**因模拟器 30 次运行零错误就声明“数学上保证绝不重复计费”；外部服务不支持 idempotency/reconcile 时必须 `UNKNOWN_OUTCOME`。

## 精简优先原则
当前访问量不明，别过早建设 Kafka/微服务/事件溯源全集群。若 DB/Worker 已满足正确性和规模要求，保持简洁；真正的差异化来自 ContentGraph 和局部失效策略。
