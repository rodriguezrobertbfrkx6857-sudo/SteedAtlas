# G0 接管记录

2026-11-01（America/Los_Angeles）。起点 5359141，原分支 upgrade/steedatlas-v2。
fetch 后远端 upgrade=e30acf7、main=9f98765，两者树内容一致。安全快进到 e30acf7，再建 feat/rag-core-major-upgrade。
唯一原有未提交文件 reports/original-video-factory-v2.json 已备份且不纳入本轮提交。

实际数据库清单见 reports/rag-upgrade/baseline.json。SQLite online backup、配置和索引副本、媒体哈希置于忽略的 runtime/backups/rag-*；媒体留在原位。没有读取或输出凭据内容，没有修改用户数据。

已阅读总纲及 README、RUNBOOK、UI_CHANGE_POLICY、CURRENT_REVIEW、LEGACY_V2_INTEGRATION、AGENT_MODE_TRUTH、FINAL_ACCEPTANCE、RESEARCH_FINDINGS 和对应路由/模型/测试。总纲提到的 11 月 1 日独立四份研究报告未在仓库发现；已有参考研究为较早架构资料，不能冒充新研究输入。

复用 Entity/Revision/Event、CPU 渲染、DAG、私有媒体 ACL；不新增平行事实数据库。原站打包入口、编译 JS/CSS、字体、图片、导航冻结。新增增强只使用独立局部适配脚本。

基线验证命令：`.venv/Scripts/python.exe -m pytest -q --junitxml=runtime/rag-baseline.xml`、frontend 中 `npm.cmd test`、`npx.cmd tsc --noEmit`。最终结果和本轮截图由 FINAL_ACCEPTANCE 汇总，未完成的检查不提前标 PASS。
