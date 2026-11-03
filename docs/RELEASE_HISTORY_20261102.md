# 百骑谱 Baiqipu / SteedAtlas

面向历史文化资料的可溯源知识检索与 Agent 工作流平台。核心是统一知识服务、自动来源获取、精确引文核验与可恢复内容生产；**默认保留原站黑金界面，不启用浅色 React 草稿。**

## 发布候选：2026-11-02

推荐入口：[启动与五分钟演示](docs/resume-readiness/DEMO_RUNBOOK.md)，原黑金站 `http://127.0.0.1:5178` / API 8006。支持空库初始化、固定版本回放、只读预检、有限刷新、非实时快照浏览和安全停止；不借用原账户和业务库。

最新代码在 `fix/resume-readiness-20261102`、[PR #1](https://github.com/rodriguezrobertbfrkx6857-sudo/baiqipu/pull/1)。实际结果见 [发布验收](docs/resume-readiness/RELEASE_ACCEPTANCE.md)、[覆盖统计](reports/resume-readiness/coverage.json)、[项目摘要](docs/resume-readiness/PROJECT_BRIEF_CN.md)、[贡献记录](docs/resume-readiness/CONTRIBUTION_LEDGER.md)。原始资产、用户数据及运行密钥未加入交付包；不直接合并主分支。

## 历史基线快照：2026-11-02 @999c692

数据与运行记录基线：`feat/rag-core-major-upgrade@999c692`。以下保留当时的审查基线，当前回归及修正后的统计以发布验收为准。

| 模块 | 已有成果 | 边界 |
|---|---|---|
| 知识档案 | 100 项名马文化档案 | 编辑条目不等于独立历史证据 |
| 自动来源 | 22 个已取得页面版本，17 个提供当前有效引文 | 实际内容主链路为维基文库；其他平台多为候选/隔离 |
| 可追溯引文 | 保存快照中 81 条机器核对引文关系，覆盖 32/100 个实体 | 不是81个独立见证，也不是专家核实的史实 |
| 检索与回答 | 实体别名/繁简、BM25、文体筛选、精确版本/原文定位 | 当前主要为检索式归属摘录，不是已接通的 LLM 综合问答 |
| Research | 真实检索、来源比较与受限自动资料补全工具 | 规则调度；LLM/Jev 未实际启用 |
| 内容执行 | 持久化 DAG、重试/取消/恢复、FFmpeg CPU 合成与下载 | 不依赖 GPU；不是视频生成模型 |
| 验证 | 原开发环境保存88项后端通过、3项前端测试及浏览器记录 | 不是生产验收或历史QA金标准 |

以上数量是有日期的数据快照；运行时还会检查来源新鲜度、权限、许可、版本和哈希。机器核对与人工审核分开，正常来源浏览不以人工逐条批准为前置条件。

**重要入口**

- [自动知识库实际验收与复现](docs/rag-upgrade/AUTONOMOUS_ACCEPTANCE_2026-11-02.md)
- [来源清单与访问边界](docs/rag-upgrade/SOURCE_PROVIDER_INVENTORY.md)
- [简历成果证据与完整审查](docs/resume-readiness/AUDIT_AND_RESUME_EVIDENCE_2026-11-02.md)
- [Codex 发布候选收尾任务](docs/resume-readiness/CODEX_RELEASE_CANDIDATE_TASKS.md)
- [本次18项依赖隔离检查](reports/resume-readiness/targeted-validation.json)：只验证证据意图分流和 Agent provider 清理，未重新运行全套88项测试，不能合并声称106项完整测试通过。

本地自动来源演示记录使用5176/8004和独立数据库副本。新clone没有用户数据库、采集缓存或私密配置；先读复现说明，不要把本地地址当公开网站。当前推荐启动方式已移到上面的发布候选入口。主分支尚未包含这些功能时，请显式选择对应开发/修复分支。

## 保留的 V2 基础

- 原站首页、导航、图鉴和视频工厂保持原有风格；浅色 React 界面仅为非默认技术草稿。
- V2 提供有版本的史料与断言、创作工程、整数帧时间轴、DAG 任务、检查点、重试、取消及私有媒体下载。
- 本地 FFmpeg CPU 链路可导出真实 MP4/SRT，不依赖 GPU、本地生成模型或付费服务。
- 文化趣味匹配、库存/预算商品推荐与历史证据通道分离，不能将商品文案当史料。
- 2026-11-01的49项后端测试记录属于历史阶段，见[当时审查记录](docs/CURRENT_REVIEW_2026-11-01.md)。最新数据请看上方自动知识库验收报告；历史报告不是今天重新运行的证明。

新环境的基础安装见[本地运行指南](docs/RUNBOOK.md)；原视频工厂集成见[兼容层说明](docs/LEGACY_V2_INTEGRATION.md)，早期验收见[原验收报告](docs/FINAL_ACCEPTANCE_A0_A12.md)。

数据库、密钥、上传文件、生成视频及依赖缓存不进入 Git。GitHub 源码仓库不能替代本机数据与交付产物备份。

## 项目结构

- `wangzhan/baiqipu.com-source-20260424-194149/`：主站前端构建产物，含图鉴、测试、抽卡收藏、商城、问答及管理页面；局部证据适配器保持原外观。
- `wangzhan/{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server/`：FastAPI、SQLAlchemy、Alembic、业务与V2知识/Agent/任务模块。
- `server/app/v2/knowledge.py`、`knowledge_api.py`：统一证据仓库、检索、归属式回答与原文服务（相对上方server目录）。
- `server/app/v2/source_acquisition.py`、`evidence_policy.py`、`research.py`：自动来源、机器引文政策与受控研究工具。
- `scripts/autonomous_sources.py`：有界采集、固定来源清单重放与隔离副本导入。
- `scripts/verify_resume_hardening.py`：不需要模型/API的两模块依赖隔离回归。
- `docs/rag-upgrade/`、`reports/rag-upgrade/`：分阶段任务、实际验收、覆盖与运行证据。
- `docs/resume-readiness/`：最新审查、简历口径与投递前收尾任务。
- `wangzhan/视频工厂/`：历史视频工厂可移植模块。
- `wangzhan/视频工厂0527_文件夹版_上传/`：历史上传版本，保留供比对。
- `wangzhan/视频工厂多agent协作/`：旧多Agent控制台页面，不等于最新ResearchAgent；缺失组件的旧控制台不能声称完整运行。
- `wangzhan/rag-proof-showcase/`、`wangzhan/video-factory-workflow/`：知识库展示和工作流独立页面。
- `wangzhan/n8n/video-factory-workflow-skeleton.json`：历史工作流骨架。
- `wangzhan/网站情况.md`：历史交接文档，路径和状态以当前代码及新报告为准。

保留原目录层级以兼容历史脚本；V2 通过新增后端模块和兼容适配器接入。

## 原归档运行方式（历史参考）

当前版本优先使用上方本地运行及自动知识库复现指南；以下保留用于理解初始归档，旧视频外部调用默认被冻结。

1. 在上述 `server` 目录安装 `requirements.txt`。
2. 将 `server/.env.example` 复制为 `.env`，填写本机配置；视频配置参考 `.env.video-factory.example`。
3. 本仓库不含用户数据库。新环境需执行 `alembic upgrade head`，并审阅 `scripts/seed.py` 后按需初始化；已有数据从本机另行恢复，不能覆盖原库。
4. 旧归档可由 `wangzhan/start-site.bat` 启动，或在server中运行 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`；不是最新自动来源演示的统一推荐入口。
5. 视频合成需要 FFmpeg；外部图片、视频、语音和发布服务需单独配置与授权。

## 边界与诚实表达

- 私有项目，不包含完整运行环境、用户数据备份、真实密钥或成片缓存。
- 主站原始 React 源码仍不完整；保留编译资源不等于已重建整个前端工程。
- 支付模块为沙箱模拟，未完成正式生产/交易安全验收。
- 机器原文核验不需要人工批准，但不证明历史事件真伪；同名提及不自动证明人物身份、主人或年代关系。
- 无独立人工QA金标准，不将自动构造查询的命中率称为历史准确率；没有宣称已验证原创算法提升。
- 无实时 LLM/Jev 或GPU视频推理验收，测试音轨不等于真实TTS，字幕不等于ASR强制对齐。
- 作品原文与现代数字版本/图片/字体的许可分别处理；见[第三方记录](THIRD_PARTY_NOTICES.md)和最新来源清单。旧第三方记录中的三条DRAFT描述仅是早期状态，不覆盖新的机器引文政策。
- 简历中个人分工、正式奖项和参赛时版本按真实材料填写，不把后续升级冒充为历史获奖功能。
