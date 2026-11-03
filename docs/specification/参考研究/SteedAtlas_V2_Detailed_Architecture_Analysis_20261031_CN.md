# SteedAtlas V2：网站、Agent 与视频工厂架构深度分析（决策草案）

> 日期：2026-10-31。范围：对 Claude《SteedAtlas — Architecture Research Report》、前次架构审查与现有百骑谱归档源码所做的工程分析。**研究与设计材料，并非已实现功能、测试报告或直接开发指令**。对原仓库进行过只读核查，未进行实际部署、视频生成或代码修改。

## 0. 已确定的目标与非目标

SteedAtlas V2 主要是**高完成度历史文化 Web 网站 + 可审查的 AI 辅助创作 + 轻量可靠工作流 + 可复现实验**。视频工厂必须支持“零视频生成模型”条件：用户素材/现有素材 → 剧本/分镜 → 音频与字幕 → 时间轴 → FFmpeg 输出。外部 LLM 可选；在 LLM 不可用时，人工编辑与确定性模板/规则仍可运行。

本轮不训练、微调或自托管视频模型；不把 Wan、ComfyUI、Temporal、Kafka、知识图谱专用数据库、向量数据库作为前置要求；不把五个逻辑 Agent 误解为五套独立模型；不进行实际付费 API 调用、不自动发布、不替用户授权外部文件写入或不可逆删除。

## 1. 源码核对与迁移风险（已读取的文件）

- `app/services/workflow_tasks.py`: 默认节点包括 `reference_input/reference_analyze/input/script/storyboard/keyframe/veo/voice/subtitle/compose/output/xhs_publish`；`default_workflow_definition` 的 `connections` 为空；`_build_execution_stages` 固定执行 `[script]→[storyboard]→[keyframe,voice,subtitle]→[veo]→[compose]→[output]`。因此画布连接不是完整可执行 DAG；旁白与字幕在同一阶段存在最终时间对齐问题。
- `app/routers/workflow.py`: 任务主要用 FastAPI `BackgroundTasks` 触发，重复运行时重置节点状态；有些输出 URL 的筛选主要排除 `mock://`、`pending://`，不能用“URL 看起来有效”代替下载、文件校验和解码。
- `app/services/video_factory.py`: 已有 FFmpeg 视频合成、模板、字幕样式与进程内线程池。既要保留已有渲染能力，也要结束两套独立调度器长期共存的现象。
- `app/services/video_factory_providers.py`: 已有外部服务、mock/off 模式。保留接口但不设为必经路径。
- `app/models/workflow_task.py`: Job 的 JSON 字段保存大量工作流状态；适合渐进迁移，但难以精确检索、并发保护和独立重试每个节点。
- `app/services/workflow_runtime.py`: Redis 为可过期事件/状态快照，不适合作为唯一历史记录。
- `app/services/ai_engine.py`: 当前主要为词项/字频 Counter 向量加余弦检索，不是语义嵌入检索。先保留 B0，对照 BM25 + 中文实体别名，测试后再决定是否引入 Dense。
- `app/routers/ai.py`: `/ai/build` 允许用户提交 `out_path`，路由内没有认证/授权检查；应禁止用户指定任意写入路径，移到管理 API。
- `app/routers/horses.py`: 更新 RAG 档案时认证用户即可调用，缺少明示编辑/管理员权限门槛，应加 RBAC 和审计。开发密钥、Webhook、远程媒体抓取及上传也须全量安全审查。
- 旧主站主要提供编译静态资源而不是完整可维护前端源码；前端须先查是否有可恢复源码，若无再渐进重建。多 Agent 展示原型的端到端后端闭环尚未证实。

**严禁**在上述理解基础上声称线上实例已经具备或缺失某能力；这是归档快照，不是生产验证。

## 2. V2 架构决策

建议模块化单体 FastAPI + React/TypeScript 主站；数据库做持久 Job/Claim/Revision 事实来源，独立轻量 Worker 做有界并发长任务，FFmpeg 为当前唯一标准渲染后端，React Flow 为可选工作流可视化组件，不把前端流程图直接当作执行保证。SQLite 本地开发可用，多个 Worker 并发生产环境优先 PostgreSQL。Redis 可以用作缓存/通知但不是唯一事实来源。服务端可以通过 SSE/WebSocket 推送进度，但以数据库状态为准。

必须区分**创作图（内容关系：断言→句子→分镜→素材→时间轴）**和**执行图（运行关系：校验→音频→字幕→渲染→QA）**。创作图编辑由服务端确定性编译为任务 DAG，校验节点类型、边、环、输入输出类型、版本及权限。

## 3. Agent 的创新点如何做实

### 3.1 角色和边界

- Research Role：仅在素材/知识来源缺失或存在历史争议时调取结构化引用与来源；提出 claim 建议，不批准历史真伪。
- Narrative Role：拟定大纲、旁白句子，产出版本化 ScriptProposal；每条有史实主张的句子需要 Claim 引用或标记为解释/创作。
- Director Role：在有剧本的条件下产出分镜，引用 Scene Bible，提出素材和时长需求，不执行视频生成模型。
- Review Role：检查证据、剧本约束、镜头元数据一致性，输出 Issue 列表；不得直接自我批准。
- Repair Role：根据 Issue 和内容版本差异提出最小 patch 与重算建议；不得直接写入或发布。

五个是逻辑角色，允许用同一 LLM、多套 schema/工具权限实现。第一版：Research（必要时）+ Narrative/Director + Review；Repair 先基于规则和依赖图执行，只有语义疑难才询问 Agent。

### 3.2 确定性 Task Controller

任务路由先由规则进行：已有经审核剧本可跳过 Narrative；仅改字幕可跳过 Research/Director；证据缺失触发 Research；跨场景约束冲突触发 Review；单纯媒体转码不调用 Agent。每个选择在 `DecisionRecord` 中记录：输入版本、触发规则、调用角色、预算上限、理由和结果。语义风险不确定时标记待审核，不允许模型继续递归发起无限任务。每个角色有 max_calls/max_repair_cycles、超时与成本限制。

### 3.3 Agent 工具模型

只读工具 `get_entity, retrieve_passages, get_claims, get_script, get_scene_bible, inspect_timeline, find_assets`；写操作变为 `propose_script_patch, propose_scene_patch, propose_claim_draft, request_review`，由服务端校验后提交。Agent 默认无删除、发布、修改审批、调用付费媒体 API 权限。所有提案包含 `project_id, base_revision, role, typed_ops[], evidence_refs[], affected_ids[], rationale, needs_review`；用乐观并发避免覆盖用户修改。

### 3.4 研究价值

研究课题一：**Adaptive Evidence-Aware Agent Orchestration**，将固定 N-agent 流水线、2-agent 简化版、规则路由 + 按需 Agent 做配对比较，评价质量、调用量、延迟、人工修改和错误。现有多 Agent 相关文献是先验基础，是否新颖需要相关工作和实测论证；不能仅因按需路由就声称原创算法。

## 4. 知识与证据模型

推荐实体（逐步建模，避免为 100 条数据引入重型图数据库）：`Horse`, `Source`, `Passage`, `Claim`, `ClaimRevision`, `EvidenceRef`, `ReviewDecision`, `SourceRights`。来源可靠程度、声明的认识论类别和审批状态分离。`epistemic_status` 区分 attested/literary/folklore/disputed/creative；`review_state` 独立。对历史依据的任何变更创建 `ClaimRevision`，同时将目标受影响图与审核策略关联到 revision，而不能只是更改一个无版本标签。

RAG 基线：原有词频检索 B0；BM25 + 中文实体别名 B1；Dense/Hybrid 为条件选项。引用必须有可打开的真实 `source_id + passage_id + version + span`。无法证实时应表现为来源不足或艺术创作，避免“正确引用”被误解为“历史真相”。

## 5. 视频工厂完整链路（无视频模型）

**入口**：新建工程（选名马/历史或文学模式/比例/时长）→ 检索引用或导入已有剧本 → 剧本编辑/审核 → Scene Bible → 分镜规划和素材绑定 → 视觉素材链与音频链并行 → 根据最终音频对齐字幕 → 统一时间轴 → FFmpeg 合成 → FFprobe 技术检查与内容审核 → 输出 MP4/字幕/工程 JSON/引用说明。

### 5.1 素材模式

`USER_UPLOAD`, `EXISTING_LIBRARY`, `STATIC_TEMPLATE/ANIMATIC`, `EXTERNAL_PROVIDER(optional)`。图片也可以通过 Ken Burns 平移缩放、淡入淡出等普通渲染获得动效；**这不是 AI 视频生成**。外部生成素材若将来加入，必须走相同 Asset 校验接口和版权策略。

### 5.2 时间顺序

旁白文本和画面规划可并行；“精确字幕对齐”依赖最终音频。无真实音频时可生成手工/估计字幕轨，但不得标注为自动 ASR 对齐。镜头最终时长由已审批时间轴确定；相邻镜头、BGM、音频混合用 FFmpeg。支持 9:16、16:9、1:1；统一 FPS、分数帧时间或整数帧索引，避免前端秒数与后端渲染不同步。

### 5.3 Scene Bible

分三层：全局名马与年代、人物、视觉风格约束；当前 Scene 属性；跨 Scene 关系/时间顺序约束。初期仅对结构化字段和文本作硬性检查，视频画面语义问题交给人工或可选外部 VLM，避免误称无 GPU 可自动识别所有视觉错误。

### 5.4 Canonical Timeline

编辑器产生可版本化的单一时间轴 JSON，包含 `fps`, `size`, `tracks`, `clips`, `asset_refs`, `start_frame`, `duration_frames`, `transition`, `caption`, `audio_mix`, `revision`。用户界面只是其投影；后端在渲染前重新验证媒体存在、权限、时长、权利和时间区间。渲染器始终只读取经验证的时间轴快照。选择一个渲染后端作为事实标准，首选沿用 FFmpeg；如评估 Rendiv，必须用相同 Timeline fixture 做真实输出对照，不要未经 POC 并存两个权威渲染器。

## 6. 工作流 Runtime 与增量恢复

### 6.1 最小必需对象

`CreativeProject`, `ScriptRevision`, `StoryScene`, `SceneBibleRevision`, `MediaAsset`, `TimelineRevision`, `WorkflowJob`, `TaskNode`, `TaskAttempt`, `TaskArtifact`, `DependencyEdge`, `DecisionRecord`, `AuditEvent`；旧 `WorkflowTask` JSON 通过版本化适配接口逐渐迁移，不直接删库。

### 6.2 任务生命周期

`DRAFT→READY→RUNNING→VERIFYING→SUCCEEDED`；可分支 `WAITING_FOR_INPUT`, `WAITING_APPROVAL`, `RETRYABLE_FAILED`, `FAILED_FINAL`, `CANCEL_REQUESTED`, `CANCELLED`, `STALE`。只允许服务端持有合法状态转换；多 Worker 更新必须有并发/租约代次保护，不以 Redis TTL 代替审计日志。外部异步 API 的未知状态单列 `UNKNOWN_OUTCOME`，不可承诺普遍 Exactly Once。

### 6.3 依赖指纹

节点复用条件需要匹配：节点类型、输入版本/Asset hash、参数、工具/模板版本、直接或间接 ClaimRevision 依赖、Scene Bible 依赖、权限/版权/有效性策略，并确认输出仍存在且可解码。依赖遗漏时保守扩大无效化范围，不能仅凭文字引用断言画面不受影响。缓存命中 != 可安全复用。

### 6.4 三层变化范围

1) 展示层编辑：字幕文字位置、封面、BGM → 通常只重建时间轴/合成；
2) 结构内容编辑：台词、角色设定、镜头规划 → 影响所涉 Scene 的素材和时间轴；
3) 证据状态编辑：Claim 内容、历史/文学类别、批准与否 → 先复核所有依赖，再决定局部重建或冻结待审。

### 6.5 正确性条件

输出成功需要：实际媒体文件存在、哈希匹配、可解码、时长/轨道可用、来自已批准的时间轴版本、必要历史依据仍有效、审核/版权条件满足。对已完成工作的保留必须有明示版本和有效性依据。

## 7. 开源集成：采用“一种功能一个主库”的原则

| 功能 | 推荐项目 | 采用方式 | 硬性边界 |
|---|---|---|---|
| 通用组件 | shadcn/ui + React/TypeScript | 直接组合改造（核实具体组件与依赖许可） | 不跨多份 UI 工程复制 |
| 内容/剧本编辑 | Tiptap Core | 优先 POC | 云端协作、商业扩展非默认免费 |
| DAG 画布 | React Flow / xyflow | 首选 POC | UI 不等于服务端调度 |
| 视频时间轴 UI | react-timeline-editor | 单独 POC | 不具备完整视频渲染保证 |
| 程序化视频编辑/渲染 | Rendiv | 备选技术 POC | Browser/Playwright 渲染占 CPU/内存，需评估；不与 FFmpeg 双主控 |
| 任务与 Agent 结构化调用 | Pydantic AI（可选） | 合适则引入 | LLM 工具输出必须通过服务端校验 |
| 多轮 Agent 图 | LangGraph | 仅必要时 | 与持久化 Worker 不重复管业务状态 |
| 视频业务参考 | Pixelle-Video、MoneyPrinterTurbo | 研究模板、合成、旁白、字幕、素材模式 | 不整体移植视频生成后端 |
| 时间线交换 | OpenTimelineIO | 后置、仅有互操作需求时 | 是剪辑元数据，不内嵌媒体、不负责渲染 |
| 视频加工 | FFmpeg/FFprobe | 现阶段唯一标准渲染 | 固定参数、进程沙盒、输出验真 |

所有公开仓库的实际 API、LICENSE、NOTICE、依赖许可证和维护状态在写入代码前重新核查。尤其 Tiptap 云服务/商业扩展、Remotion 非 OSI 开源许可、Rendiv 的兼容性需分开判断。**不要因为有开源项目就自动增加安装和维护成本。**

## 8. 前端产品结构与用户旅程

主站：Home、Catalogue、HorseDetail、Sources、Ask、StudioProjects、ScriptEditor、Storyboard、Timeline、WorkflowMonitor、AssetLibrary、ReviewQueue、UserProfile、AdminCMS。收藏、抽卡、文化商城等原有功能保留但放到次级入口，不以删除为改版前提。公共站和专业工作台统一品牌与设计 Token，Guided 和 Expert 只是同一工程数据的不同视图；避免两套前端各实现一套工作流。Web 产品需满足键盘操作、字幕、焦点和移动端需求。

推荐展示动线：名马档案→打开史料→创建项目→剧本和引用→分镜→素材时间轴→渲染出片→点击任一字幕回看相关来源；中途编辑一个字幕或退回一个 Claim，展示局部受影响范围。

## 9. 研发顺序与迁移验收

| Gate | 主要内容 | 不可跳过的验收 |
|---|---|---|
| G0 | 只读清点、可构建性、数据库备份与回退、危险接口修复 | 旧数据和路由有清单；备份可恢复；高风险漏洞有测试 |
| G1 | 恢复/重建可维护 React 源码和设计系统 | 主要页面可编译；旧业务保留；移动端与导航可用 |
| G2 | 内容后台、100 马目录、三份精品档案、来源与版本 | 可编辑、可审计、可检索、准确打开来源 |
| G3 | 项目数据模型、Scene Bible、脚本/分镜/素材 UI | 项目导入导出和乐观并发编辑成功 |
| G4 | Timeline→FFmpeg 渲染链路、字幕、音频 | 不需要视频模型与 LLM，能够使用给定素材完成真实 MP4/SRT/封面导出，输出已解码验证 |
| G5 | DAG 和独立 Worker，Agent 角色/控制器 | 故障注入后能恢复、取消、局部重跑；真实工具轨迹可核验 |
| G6 | 证据依赖更新及创新实验 | 有强基线、失败样本、全指标和可复现脚本 |
| G7 | 全站回归、性能/SEO、安全、文档与演示 | 单仓可部署、构建和回退，结果与模拟功能明示 |

G3–G5 可以并行做原型，但每个合并必须经过集成测试，不能把未连通页面或 Mock 结果算作正式交付。

## 10. 研究验证方案：让“创新”可证伪

**Track A — Adaptive routing**：固定全部角色 vs 单规划+工具 vs 规则按需角色；相同模型和任务集，记录任务完成、事实性、角色调用次数、延迟、人工修订次数。若没有显著提升，保留最简单可行策略。

**Track B — Cross-scene consistency**：无 Scene Bible vs 全局固定设定 vs Global+Scene+Constraint；使用人工检查的跨场景文本一致性和样例画面审核，分离结构化约束与多模态感知任务。

**Track C — Evidence-aware changes**：全量重跑 R0 vs 依赖缓存 R2 vs 知识版本和状态完整的强基线 R2+ vs 声称语义增强的 R3；对修改知识类别、撤回断言、改字幕、换 BGM 等真实操作进行对照。特别记录错误复用/错误失效、额外处理量及编辑耗时。R3 优势未知，无法证实则当成领域工程实现。

所有模拟与真实测试分开汇报。三个旗舰条目不足以支撑广泛泛化结论，应扩大标注样本或谨慎限定结论。不可凭 30 次故障试验零重复就宣称 Exactly Once。

## 11. 最终交给 Sol 的不可妥协原则

- 不做 GPU/视频模型训练或部署；不开启付费云媒体调用；新增 Agent 模型调用需要已有授权/配置且尊重成本上限。
- 优先复用已经存在的 FastAPI/SQLAlchemy/FFmpeg/文化数据和原业务，不盲目重写。
- 不损坏旧站和数据；先建可恢复基线，迁移过程用兼容适配与测试。
- 一个权威 Project、Timeline 和 Workflow 数据模型，不能有多套互相冲突的任务状态。
- 不把前端图谱、进度动画、空 URL 或 Mock 结果当作真实工作完成。
- 直接复用第三方代码前检查版本、LICENSE、NOTICE、依赖与维护可行性。
- Agent 只提出改动，实际提交由服务端校验和授权；发布、删除及可能产生费用的操作设显式门槛。
- 交付每个 Gate 的源码改动、测试、实际操作截图/媒体文件、失败清单、回退方式和剩余问题，不编造成效指标。

## 12. 本轮仍未核实、需要 Sol 首先调查的地方

前端源码能否从原项目其他历史分支恢复；当前站点是否有可用的多 Agent API；旧视频工厂的实际素材与导出功能在干净环境能否运行；现有图鉴数据中每条的来源可追溯程度；生产环境配置、媒体存储及部署拓扑；第三方组件的具体版本许可证和 API 兼容性。不能从归档直接推导出线上能力。

## 13. 本轮引用与技术资料（供后续独立核查）

- Claude《SteedAtlas — Architecture Research Report》（用户提供，2026-10-31），第 4–16 章；报告为概念研究，不包含真实实施成绩。
- 私有百骑谱 GitHub 仓库的上述源码模块（仅只读审查；不要向外部 Claude 研究任务暴露私有路径）。
- https://github.com/xyflow/xyflow
- https://github.com/ueberdosis/tiptap 和 https://tiptap.dev/docs/editor/getting-started/overview
- https://github.com/xzdarcy/react-timeline-editor
- https://github.com/thecodacus/rendiv
- https://github.com/pydantic/pydantic-ai
- https://github.com/ATH-MaaS/Pixelle-Video
- https://github.com/harry0703/MoneyPrinterTurbo
- https://opentimelineio.readthedocs.io/en/latest/

**审查结论**：本轮可以立项为 CPU-first 网站 V2 升级项目，技术核心是结构化创作工程、受控自适应 Agent 和知识感知增量更新；不需要模型训练。下一步再编制正式开发指令与验收矩阵，而不是让 Sol 无范围限制地“把所有开源组件全接一遍”。
