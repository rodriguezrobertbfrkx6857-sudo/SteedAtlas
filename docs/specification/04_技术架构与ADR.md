# V2 系统架构与技术决策（ADR）

## 系统拓扑
```
Browser (React/TypeScript)
 ├─ Public catalogue / source passage / grounded Q&A
 ├─ Guided creation studio: script/storyboard/assets/timeline
 ├─ Expert studio: visual DAG/agent trace/review
 └─ Admin: sources/claims/rights/permissions
             |
             v
FastAPI API + Auth/RBAC + Validation
 ├─ Catalogue/Knowledge/Retrieval
 ├─ CreativeProject & Versioned Content
 ├─ Agent Gateway & Deterministic Task Controller
 ├─ Workflow Compiler & DAG Policy
 ├─ Asset/Timeline/Media Verification
 ├─ Review / Rights / Audit
 └─ Compatibility API for existing frontend
             |
       SQLAlchemy / Alembic
             |
   DB (dev:SQLite; recommended for concurrent workers: PostgreSQL)
      |                        |
      v                        v
Worker(s) (CPU)             Artifact directory/Object store
  ├─ FFmpeg/FFprobe          ├─ media + SHA-256 + provenance
  ├─ subtitle/timeline       └─ public only after approval
  └─ optional external LLM/TTS/Media adapters (disabled by default)
```

## ADR-001：一套业务后端
继续 FastAPI/SQLAlchemy；禁止同时创建独立的 Next.js BFF、新微服务和新数据库来维护相同业务状态。若现有多 Agent Next.js UI 更优秀，可以移植组件或作为薄前端，但它不能成为第二权威后端。

## ADR-002：工作流不等于 Agent
- Content DAG：Project → Script/Claim → Scene → Asset/Timeline；解释哪些内容受修改影响。
- Execution DAG：Typed Node → Attempt → Artifact；决定可以执行哪些任务。
- Agent 是提出/审核内容变更的**有类型行动**；DAG 执行属于可靠工程层。
- 通过确定性 Compiler 从 Creative Project Revision 编译 Execution DAG；禁止直接用不受信任的 LLM 文本作为执行定义。

## ADR-003：单一 Canonical Timeline
用户编辑/保存/回放/渲染依赖一套版本化时间轴 JSON；React 时间轴只是视图、FFmpeg 是默认渲染器。需要一个基于媒体真实时长的时间单位约定（整数毫秒或 rational frame ticks），防止浮点漂移。确定音频时长后才能精准对齐字幕。

## ADR-004：AI 可选而非核心依赖
默认工具可用：手动剧本、搜索/证据、图像动画、素材裁剪、FFmpeg 合成、SRT、质量检查。AI Agent 运行时由 Provider Adapter 提供，明确 `LIVE`, `RULE_BASED`, `MOCK_TEST`, `UNAVAILABLE` 模式；用户界面据实标识。

## ADR-005：开源复用的界限
优先已有成熟组件和原项目工具；每个领域一种主依赖。先做独立 POC；若 OSS 与当前架构不符则退回自有最小实现。保留第三方许可证、版本和 NOTICE。

## ADR-006：最小持久执行层
先比较 (A) DB-backed Worker 与 (B) 轻量队列/成熟运行时 POC，在故障正确性下选运营复杂度更低者。禁止为了“自研”先构建庞大的分布式任务框架。DB 为权威状态；Redis optional。

## ADR-007：网站能在弱配置运行
一般 CPU + RAM + FFmpeg 即可本地开发/出片。复杂视频渲染需要 CPU 时间和内存但不是 GPU 必需。API 调用/付费/硬件扩展均需用户单独授权。

## ADR-008：史料支持不等于历史真实性
每个 Claim 的来源可靠性、证据强度、认识论类别及审稿状态分开存储；LLM 不得自动把生成内容标为已证实。研究记录始终区分“文献支持”和“客观真实”。

## ADR-009：保守失效判断
显式依赖 + 内容哈希 + 元数据状态 + 规则；遇到未知依赖或语义变更时 `REVIEW_REQUIRED` 而不是假定 `REUSABLE`。优先正确性，再优化成本。

## 最小技术栈
- React + TypeScript；可以继续当前前端构建工具，除非理由充分才迁移；shadcn/ui/Tailwind 是候选而非强制重构所有样式。
- React Flow：可视化节点，不提供后端执行。
- Tiptap：剧本编辑器候选，使用基础开源模块。
- React Timeline Editor：交互时间轴候选，需验证与 canonical schema 转换。
- Python/FastAPI/Pydantic/SQLAlchemy/Alembic；PostgreSQL 面向生产并发、SQLite 开发可用。
- FFmpeg/FFprobe：默认渲染和技术校验。
- pytest、Playwright、TypeScript typecheck、CI。

## 必须保留的架构取舍证据
在 `docs/decisions/` 新建/更新 ADR：问题、选项、测量标准、POC 结果、选择、版本/许可证、回退办法。任何未经测试的技术选型一律标注 *proposed*。
