# 百骑谱 / SteedAtlas

面向名马历史文化的可溯源知识检索与内容工作流平台。

![百骑谱原站界面](docs/screenshots/home.png)

## 核心功能

- 名马文化图鉴、中文别名与 BM25 检索。
- 来源版本、文本哈希、引文区间校验与原文溯源。
- 受限 Research 工具调度、来源补全与覆盖检查。
- 持久化 DAG、重试、取消、恢复及 FFmpeg CPU 视频合成。

## 启动与演示

请按 [五分钟演示与启动说明](docs/resume-readiness/DEMO_RUNBOOK.md) 初始化独立环境和空库。推荐原站端口5178、API端口8006。

环境：Windows、Python 3.13、Node 22、FFmpeg；固定依赖见根目录 requirements-resume-windows-py313.lock。

## 版本与验证

本公开仓库为2026-11-02发布源码快照，来自原工程提交 `57f76fd`，不包含原私有仓库历史、用户数据库、运行密钥及生成媒体。原目录结构保留以兼容启动脚本。

历史独立环境验收：104项后端测试、3项前端测试、类型检查及构建通过。详见 [验收报告](docs/resume-readiness/RELEASE_ACCEPTANCE.md) 和 [项目技术摘要](docs/resume-readiness/PROJECT_BRIEF_CN.md)。本次公开整理未重跑完整套件。

100项编辑档案不等于100项已核实史实；机器引文核验不替代史学判断。现有回答主要是检索式摘要，实时LLM综合问答、生产部署和跨平台验收未完成。历史报告中的私有仓库、分支、运行目录及未公开状态描述是当时记录。

## 许可与资料

本次公开不额外授予统一开源许可。第三方代码、图片、字体与资料保留各自权利，详见 [第三方说明](THIRD_PARTY_NOTICES.md)。不将历史素材视为可自由再分发资源。
