# 本轮交付与复现

当前可访问的原站升级演示：[http://127.0.0.1:5175](http://127.0.0.1:5175)，API文档：[http://127.0.0.1:8003/docs](http://127.0.0.1:8003/docs)。仅绑定本机。使用 `runtime/rag-demo-path.txt` 指定的隔离数据库副本；原8002/5173环境和原始业务库保留。

这是一版可运行的统一证据核心。全量任务书尚有未完成项，详见 [完整验收报告](FINAL_ACCEPTANCE.md)。真实知识库仍为3条DRAFT候选，无法诚实演示“已由专家批准的历史结论”；能够演示待核原文、正确拒答、编辑浏览与真实本地Research工具。

## 演示步骤

1. 打开原站首页，保留黑金导航和图鉴。
2. 打开AI客服，在原输入框问“赤兔的史籍出处是什么？”；回答明确证据不足。
3. 页面下方“知识与原文证据”显示待核来源，点击可打开原文高亮、Claim/Passage版本与审核状态。
4. 使用原站账户登录。在证据区输入“赤兔和的卢的来源比较”，点击“研究与来源比较”，查看实际search/compare/coverage调用及待审提案。
5. 原视频工厂继续使用本地CPU流程。已有本轮[MP4](../../deliverables/rag-acceptance.mp4)与[SRT](../../deliverables/rag-acceptance.srt)；测试音轨/字幕不冒充TTS或ASR。

本轮截图在 reports/screenshots/rag-upgrade/。`stable-current-home-desktop.png`、`stable-current-home-mobile.png`为稳定原站首页；`chat-evidence-desktop.png`、`exact-citation.png`、`research-tools.png`分别展示证据、引用和真实工具。

## 启动与验证

在项目根目录运行：

```powershell
# 当前演示已启动，不必重复启动。
# 以后端口空闲时启动同一个项目内副本：
.\start-rag-demo.ps1

# 完整测试（独立临时库）
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/rag-upgrade/final-tests.xml
npm.cmd --prefix frontend test

# 原站浏览器、真实聊天/引用/Agent
.\.venv\Scripts\python.exe scripts/rag_browser.py --phase after --web http://127.0.0.1:5175
.\.venv\Scripts\python.exe scripts/rag_ui_flow.py

# 实验：固定公开仓库语料+本地副本，不调用模型
.\.venv\Scripts\python.exe experiments/rag_candidates.py
.\.venv\Scripts\python.exe experiments/rag_evaluate.py

# 重新从原库创建唯一副本，测试迁移/回滚，不触碰原库：
.\.venv\Scripts\python.exe scripts/rag_copy_verify.py
```

`rag_copy_verify.py`生成新的副本指针；若已有服务运行，需先停止本项目对应的演示API/Worker，再启动以读取新副本。启动脚本检查8003/5175已占用时会拒绝重复启动。项目原RUNBOOK中的8002/5173仍是常规模式；若切换到原运行库，应先备份并显式运行 `scripts/rag_migrate.py --apply`，本轮没有替用户执行这一步。

无本地运行数据库的新环境，先依照原RUNBOOK执行 `scripts/run_v2.py init`。它创建空库与DRAFT种子，不能恢复用户账户/媒体。随后才能运行副本演示验证。

## 回退与保护

- 私有备份路径记录于 reports/rag-upgrade/baseline.json；完整哈希清单仅在忽略的runtime/backups中。不要将其加入Git。
- 原有 `reports/original-video-factory-v2.json` 未提交修改保留，本轮没有暂存它。
- `RAG_CORE_ENABLED=0`可以回退旧聊天；即使有API key，旧付费生成也默认关闭。不得在没有用户授权时设置付费授权变量。
- 新功能复用V2 Entity/Revision/Event，没有删除旧表；代码可通过普通revert回退。任何真实库downgrade/删除仍需另行批准。
- 移除index.html中的evidence-adapter脚本引用即可撤回局部UI增强；原编译JS/CSS/字体/图片未变。
- 当前所有提交仅在本地feature分支。未推送、未公开部署、未调用外部模型。

验收JSON、JUnit、对照实验原始结果、Agent工具日志、视觉差异和业务冒烟均位于 reports/rag-upgrade/。截图和媒体依照原仓库策略保持本地忽略文件，可以在此电脑直接打开。
