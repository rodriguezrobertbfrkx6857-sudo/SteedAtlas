# SteedAtlas / 百骑谱 V2：面向 GPT-6.1 Sol 的架构蓝图（研究与开发交接草案）

> 状态：规划草案，非已实施功能；2026-10-31。依据：Claude《SteedAtlas Architecture Research Report》、此前《Comprehensive Architecture Audit》及对百骑谱私有 GitHub 源码的只读检查。源码静态检查不等于运行/线上验证。此文档不授权访问、改写、部署任何仓库；实际开发必须由用户另行明确工作区与权限。

## 0. 目标、边界与总策略

- 保留中文产品“百骑谱”的获奖业务和原始内容；SteedAtlas 只是英文研究代号。
- 产品主线：精品历史名马图鉴 → 可核验引用的问答 → 三分镜视频制作 → 专业工作流与产物证据报告。
- 科研主线：Knowledge-Conditioned / Evidence-Aware Recovery；优先比较 R2+ 强基线与 R3，绝不先宣称原创或性能优势。
- 技术主线：**CPU-first / Mock-first / No-training-first**。默认不依赖 GPU、不需要训练。真实云端视频由用户明确批准后小额验收。
- 成功条件：单一可启动工程、可恢复工作流、可核查证据链、完整实验基线、真实与模拟运行严格标记、视觉设计统一。
- 禁止项：推倒旧系统、操作未授权目录、删除历史素材/提交/竞赛材料、隐式计费、泄露密钥或未授权媒体、把 Mock 当作真实生成、编造测试/收益数据。

## 1. 推荐系统拓扑

```text
用户 / 内容审核员 / 研究员
       │
       ▼
Frontend：文化图鉴 + AI 问答 + Guided Studio + Expert DAG + 研究仪表板
       │ HTTPS / authenticated API / SSE or WebSocket only where needed
       ▼
FastAPI modular monolith（继承既有 FastAPI、SQLAlchemy、Alembic）
  ├─ IAM / Security / Content & Catalogue
  ├─ Evidence Store：Source → Passage → Claim → ClaimVersion → EvidenceRef
  ├─ Retrieval：alias + BM25；Dense/Hybrid only upon benchmark evidence
  ├─ Planner / Critic：最多两个语义判断 Agent，严格限制副作用
  ├─ Workflow Compiler：经类型校验的 storyboard → 显式无环 DAG
  ├─ Durable Runtime：Job/Node/Attempt/Lease/Outbox/Idempotency/Budget
  ├─ Media Adapter Registry：Mock / existing API providers / local ComfyUI optional
  ├─ QA & Review：事实来源、媒体有效性、发布审批、成本限制
  └─ Tracing & Experiments：运行轨迹、故障注入、R0/R1/R2/R2+/R3
       │
       ├── PostgreSQL（持久任务、知识、审计、权限；开发可 SQLite 单机降级）
       ├── Worker（独立进程、心跳、fencing token、状态对账）
       ├── File/Object Store（哈希+ACL；本地开发文件，生产可 S3/MinIO）
       ├── Redis（可选缓存和通知；绝非唯一任务事实源）
       └── 外部服务：LLM/视频/TTS API；可选 ComfyUI/Wan
```

> 单体是领域模块与 API 统一部署，不意味着用 FastAPI BackgroundTasks 执行长时间付费工作。DB 与 Worker 的任务所有权必须设计清楚；不可出现多个运行时互相覆盖状态。

## 2. 各子系统的架构决策

| 子系统 | 沿用现有 | 推荐框架/方案 | 必须验证的边界 | GPU |
|---|---|---|---|---|
| 公共站与创作台 | 编译版 React、静态资产、工作流页 | 恢复 React 源码；必要时建立 React+TypeScript+Vite 可维护工程；React Flow 做 DAG 画布，已有站点平滑过渡 | 源码恢复、路由兼容、SEO、移动端、WCAG | 否 |
| API/业务 | FastAPI/SQLAlchemy/Alembic、用户、名马与订单 | 模块化单体，Pydantic typed contracts，保留现有 API 兼容层 | 迁移、权限、回滚、历史业务回归 | 否 |
| 可信知识 | 100 条名马基础语料 + 18 条视频专用素材 | Source/Passage/ClaimVersion/EvidenceRef；先 3 个精品案例 | “文学/史籍/传说”标签与审核状态分开；引用精确到段落 | 否 |
| RAG | 自有词频余弦检索 | BM25+别名+结构化过滤首选；可选 multilingual embedding / RRF | B0/B1/B2/B3/B4 对比，拒答与引用真实性 | CPU 够用 |
| 语义 Agent | 现有 LLM API/回退 | Planner+Critic 与确定性工具；模型适配器可 Mock/OpenAI-compatible | Agent 不能直接审批/消费/写入不可信来源 | 本地无须；云端 API 可能计费 |
| DAG 编译 | 固定 stage 列表 + workflow_definition.connections | 有向无环、typed inputs/outputs、循环/依赖/未连接验证 | UI 编辑 DAG 必须真影响后端执行 | 否 |
| Durable Runtime | FastAPI BackgroundTasks、DB states/Redis runtime snapshot | 两路 POC：A DB-backed Lease+Outbox Worker；B 成熟编排框架（LangGraph/Temporal）+ 自有 side-effect ledger；经故障测试选定唯一状态事实源 | `UNKNOWN_OUTCOME`、fencing、幂等、预算、并发 | 否 |
| 视频生成 | 既有 provider 模块 + FFmpeg | 保留适配器；参考 Pixelle-Video、MoneyPrinterTurbo，不整库替换；视频 API 统一 submit/poll/fetch/verify | real/mock/dry-run 明确标识；账单与 URL 安全 | 云 API 不需要本地 GPU |
| 后处理与质检 | 既有 FFmpeg/TTS/字幕 | ffmpeg/ffprobe+PySceneDetect 镜头检测；VideoLingo 仅需要词级对齐时接入 | 解码、时长、静音、字幕同步/越界与来源标签不能混为一项 | 可 CPU |
| 研究与质量 | 旧测试脚本，缺标准持续集成证据 | pytest、属性/并发测试、模拟供应商、故障注入、置信区间与数据集 | 模拟结果与实付测试不可混写 | CPU |

## 3. 统一核心契约

- `Source`：来源身份、版本、语言、权利、出版信息、内容哈希。
- `Passage`：具体可引用段落或页码位置，版本及哈希。
- `Claim` / `ClaimVersion`：不可变版本、`epistemic_status` 与 `review_state` 独立、引用证据集合、编辑记录、使用模式约束。
- `EvidenceRef`：Passage→Claim 的 SUPPORTS/CONTRADICTS/MENTIONS 关系，人工审核证据。
- `Job` / `TaskNode` / `Attempt`：显式依赖、输入版本、运行策略、产物哈希、租约代次、失败类别、重试预算。
- `Artifact`：产物 ID 与文件 hash 分离；owner/ACL/rights/TTL/storage_uri/QA 元数据。
- `ProviderCapability`：幂等键支持、客户端引用查找、按任务查询、回调签名、取消、结算语义。
- `ProviderSubmission`：本地调用前记录，未知提交状态进入 `UNKNOWN_OUTCOME`，禁止悄悄重复付费。
- `CostLedger`：Estimate → Reserve → Settle/Release / Possibly Billed，事务一致，不能余额双算。
- `ReviewDecision`：带审批人、范围、期限和知识版本的独立记录；不可由模型文本伪造。
- `ProvenanceEdge`：Passage→Claim→Sentence→Beat→Prompt→Artifact，附直接/间接依赖；不确定时按保守失效处理。

## 4. 运行时安全语义

- **外部 exactly-once 不作普适承诺**：无供应商幂等键或可查询 client_ref 时，进程崩溃后的提交结果可能未知；进入 `UNKNOWN_OUTCOME`，暂停自动重复提交，要求对账/用户确认。
- Worker 通过 DB transaction + lease epoch/fencing token 领取与提交任务；失效 Worker 不能覆盖新执行者。
- 用户取消后，回调只做有权限的审计记录，不推进已取消任务；存储保留遵守 TTL/ACL。
- 可视化流程不是执行语义：只有通过 schema 校验的 connections 和节点参数才能编译 DAG。
- 任何节点成功必须有真实可读取、可解码、版本/时长匹配的产物；`mock://` / `pending://` 必须保持虚拟标识，绝不伪装成可播放 MP4。
- 支持来源更新后分析直接及隐含受影响节点；无法证明无影响则保守重算或人工核验。

## 5. 开源项目优先级

| 项目 | 作用 | 决定 |
|---|---|---|
| React Flow (xyflow) | 专业 DAG 画布 | UI 源码可维护后优先考虑 |
| Pixelle-Video | 分镜/模板/可替换生成节点 | 研究与有条件复用，不替代百骑谱执行系统 |
| MoneyPrinterTurbo | 低成本稳定出片/字幕/FFmpeg | 工作流与媒体 Baseline；按许可证适当复用 |
| LangGraph | 代理状态管理、审批、checkpoint | 作为 Runtime POC/规划回路候选，不预设胜负 |
| Temporal | 可靠长时任务执行 | 候选对照，可能增加部署负担 |
| PySceneDetect | 镜头/切点检测 | 可以作为独立 QA 工具，非全面质检 |
| VideoLingo | ASR/词级字幕对齐 | 真有需求再引入独立服务 |
| ComfyUI | 本地/远程可复用多模态模型节点 | 可选独立服务，许可证与模型授权单独核实 |
| Wan2.2 | 开源本地视频模型 | V2 主体完成前不作为依赖 |

所有复用应保留上游 GitHub URL、版本 SHA、LICENSE/NOTICE、调用边界、回滚办法。API 价格与模型可用性必须现查，不使用长期硬编码断言。

## 6. 科研评测协议（预先设计，结果为空）

**可靠性主实验**：R0 全流程重跑、R1 有持久检查点、R2 普通 DAG 哈希缓存、R2+ 知识版本/元数据感知的强增量缓存、R3 证据语义感知安全复用；R4 成本/质量策略仅探索。共享模拟供应商、相同种子、相同任务结构和故障。

**知识实验**：B0 原词频，B1 BM25+alias，B2 Dense，B3 Hybrid-RRF，B4 带逐句证据审核的规划；按可回答/不可回答问题分别评估引用准确、事实支持和拒答。

**Agent 消融**：S0 单规划调用+工具、S1 Planner+Critic、S2 多决策 Agent。评估成功率、token/预算、延迟、人工审核和事实错误，不能假设多 Agent 必胜。

**故障注入**：429/5xx、submit 后崩溃、未知状态、重复/乱序回调、租约失效、输入知识变更、断言类别修订、视频损坏、产物缺失、用户取消、跨用户错误访问、预算竞争。所有关键不变量均需确定性测试，不仅用 30 seeds 统计。

**主指标**：错误复用绝对数、错误复用机会数、错误拒绝复用、额外付费调用、每个合格成片的全成本、任务成功率、恢复率、p50/p90 延迟、人工审核时间；技术性视频指标与人类视觉质量分开。

**学术诚信**：R3 若未超过 R2+，照实报告为领域系统化工程而非原创最优算法；所有 Mock、预渲染、真实调用、未经测试均须明确标注。

## 7. 算力和成本分层

- **Tier 0 / CPU（必须先完成）**：4–8 CPU 核、建议 16GB RAM、SSD；UI、FastAPI、PostgreSQL、DAG、Agent Mock、BM25、100 条知识内容、失败注入、FFmpeg 测试样片。资源是开发建议值，不是经过本系统压测的最低配置。
- **Tier 1 / 可选轻推理**：小型 embedding/ASR/图片模型可 CPU 或小 GPU，根据基准决定。云 LLM 需要网络与 API 预算，不消耗本地 GPU。
- **Tier 2 / 真实高质量短片**：云视频 API（本地零 GPU 但付费）或受支持 GPU 的本地 ComfyUI/视频模型。先以免费/预制素材与 FFmpeg 做真实文件回归，再按用户批准的小预算测模型。
- **Tier 3 / 训练和微调**：当前不需要；仅在发现已有检索/生成模型无法满足有证据的科研目标时单独申请算力。
- **参考**：Wan2.2 官方 TI2V-5B 原生示例说明至少 24GB VRAM，A14B 原始单卡示例约 80GB VRAM；社区压缩方案不可直接当作已验证资源保障。见 https://github.com/Wan-Video/Wan2.2。

## 8. 适合 Sol 的升级阶段与验收门

| 阶段 | 核心工作 | 退出条件 |
|---|---|---|
| G0 基线与保护 | 仓库清单、备份/分支、依赖/密钥清查、最小启动、已有数据盘点 | 无破坏改动；明确真实可运行/缺失组件 |
| G1 P0 安全 | 受限知识写入、路径/SSRF/权限/默认密钥、隔离媒体文件 | 自动化权限与安全回归通过 |
| G2 工程规范 | 恢复或渐进重建前端源码、后端整理、DB 迁移、mock adapter、标准 pytest/CI | 主站和旧业务不回归；CPU 一键可运行 |
| G3 内容与 RAG | 三个精品档案、证据/断言版本、BM25 和评测集 | 问答可定位精确出处，文学/历史区分，拒答可测试 |
| G4 Durable DAG | 两个 Runtime 小 POC 决策，独立 Worker，DAG、Attempt、预算与未知提交状态 | 重启/崩溃/重复回调/取消/并发测试通过 |
| G5 媒体闭环 | 恢复现有 provider 和 FFmpeg，接入 QA 与 Guided/Expert 视图 | CPU Mock/预制素材可输出可解码 MP4，详细标识模拟与真实 |
| G6 科研框架 | R0/R1/R2/R2+/R3、故障注入、消融、数据报告 | 所有结果可重复、负面结果可如实保留 |
| G7 最终交付 | 演示、README、安装测试、贡献说明、文档与变更报告 | 从干净环境可复现核心 demo；权利、安全、发布审查完成 |

**阻断规则**：涉及付费调用、实际发布、权限范围外目录、不可逆删除、强制推送/重写历史、系统级安装时必须用户授权。其他普通有权限目录内开发可按执行策略持续推进，但每阶段提交报告、测试证据和回滚点；P0 安全失败不应绕过直接上线。

## 9. 真实仓库迁移关注

- 后端归档 `server/app/services/ai_engine.py` 是 `Counter(_tokenize(text))` 稀疏词频检索，不可称神经 Dense。
- `server/app/services/workflow_tasks.py` 的 `_build_execution_stages()` 固定 stage 列表；目前前端 graph 连接不等同真实 DAG 调度。
- `server/app/routers/workflow.py` 用 `background_tasks.add_task(...)` 触发较长流程，重跑重置 node_states/result_payload；不等于完整跨进程持久恢复。
- `server/app/routers/ai.py` `/build` 允许指定 `out_path` 且路由自身未授权；`server/app/routers/horses.py` 的知识编辑端点需角色授权；`server/app/config.py` 存在开发默认 secret。
- 主站大部分保存为编译后 React 文件；多 Agent Next.js 界面缺部分 backend/types 依赖；不能以静态截图证明端到端运行。
- 大量重复归档只能在构建映射、依赖审计、历史备份及用户许可后有选择地清理，不能直接批量删除。

## 10. 6.1 Sol 交接时必须附带的产物

`ARCHITECTURE_DECISIONS.md`、`EXISTING_SYSTEM_BASELINE.md`、`SECURITY_AUDIT.md`、`DATA_AND_PROVENANCE_SCHEMA.md`、`RUNTIME_POC_COMPARISON.md`、`MEDIA_ADAPTER_MATRIX.md`、`OPEN_SOURCE_LICENSES.md`、`EVALUATION_PROTOCOL.md`、`TEST_EVIDENCE.md`、`KNOWN_LIMITATIONS.md`、`CHANGELOG_AND_ROLLBACK.md`、`FINAL_REPORT.md`。

以上报告应使用中文；源码、协议与原始论文标题可保留英文。原 Claude 报告本身只作为理论研究材料，不表示任何新模块已经完成。
