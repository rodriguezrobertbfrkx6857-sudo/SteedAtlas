# 视频工厂清单（2026-05-17）
更新时间：2026-05-17（Asia/Shanghai）

## 1. 前端文件

1. `frontend/workflow-studio/index.html`
2. `frontend/workflow-studio/app.js`
3. `frontend/workflow-studio/styles.css`
4. `frontend/horse-rag/index.html`
5. `frontend/images/chitu.png`
6. `frontend/images/wuzhui.png`
7. `frontend/images/dilu.png`
8. `frontend/images/hanxue.png`
9. `frontend/images/jueying.png`
10. `frontend/route-shell-reference.jsx`

## 2. 后端文件

1. `backend/app/models/workflow_task.py`
2. `backend/app/schemas/workflow.py`
3. `backend/app/routers/workflow.py`
4. `backend/app/routers/horses.py`
5. `backend/app/services/workflow_tasks.py`
6. `backend/app/services/workflow_runtime.py`
7. `backend/app/services/video_factory_providers.py`
8. `backend/app/services/video_factory.py`
9. `backend/data/video_factory_rag.json`
10. `backend/data/legendary_horses_top5.json`
11. `backend/data/legendary_horses_batch1.json`
12. `backend/data/legendary_horses_batch2.json`
13. `backend/optional-stubs/ai_engine.py`

## 3. 配置文件

1. `config/video-factory.env.example`
2. `config/integration-snippets.md`
3. `config/requirements-extra.txt`

## 4. 本次更新点

1. 画布重排：右侧节点不再挤压重叠，上下分层间距加大，连线更清晰。  
2. 画布可整体平移：按住画布空白区域可拖拽移动整张画布。  
3. 节点主要内容区新增故障定位：  
   - `执行失败`：显示失败节点与错误摘要  
   - `疑似空输出`：节点结束但没有主要输出时给出定位提示  
4. README 已补充画布操作、接入流程和排错步骤。
5. 参考素材上传状态修复：  
   - 前端“已上传”判断由 `mediaUrl` 扩展为 `mediaUrl/localPath` 任一可用  
   - 兼容上传回包字段：`camelCase` 与 `snake_case`  
   - 后端未提供上传路由时，前端保留本地素材选择并提示缺失接口
6. 文档增强：新增“模板系统版本化”完整章节，覆盖保存版本、应用版本、删除版本、团队协作建议。  
7. 文档增强：新增“小红书节点产品化”完整章节，覆盖连接测试、Cookie 有效期检测、草稿发布、定时发布、失败回滚提示与排错。  
8. 集成文档增强：`config/integration-snippets.md` 新增模板版本接口与小红书预检接口调用示例，便于接入方直接联调。
9. 新增 `RAG马库` 页面：`/horse-rag/` 可浏览 100 匹名马，点击单马可查看马匹生平、对应人物故事和视频创作建议。
10. 视频工厂内容输入节点已接入 RAG 马库：接口可用时主角名马下拉自动扩展到 100 匹，接口不可用时回退默认 5 匹。
11. 打包目录新增默认图片资源 `frontend/images/`，避免迁移后预览图丢失。
12. RAG 马库详情页重排：图片与信息区分栏固定，不再互相覆盖；移动端自动改为单列。
13. 100 匹马资料增强：简介、马的一生、主人的一生均已扩写，便于视频工厂检索和页面阅读。
14. 视频创作台文案弱化工具感：隐藏面向用户的模型/API式表达，保留原有配置和生成功能。
15. RAG 马库接口说明补齐：接口按当前 `backend/data/legendary_horses_*.json` 文件生成响应，不保留旧数据缓存；验证以 `GET /api/v1/horses/rag-library?size=200` 返回 `total=100` 为准。
16. 打包目录数据同步核对：三份名马 JSON 与运行环境最新数据哈希一致，`frontend/horse-rag/index.html` 与最新 RAG 页面哈希一致，本次无需再复制覆盖。
17. 节点主要内容区视觉升级：新增状态、进度、重试、耗时、故障原因、产物链接等排错信息，卡片排版更完整。
18. RAG 马库详情页新增编辑入口：可登录后编辑故事资料、镜头参考、视觉关键词和旁白种子，并写回后端 JSON。
19. 小红书节点补齐连接测试提示、Cookie 配置状态、自动评论和评论采集字段，后端会把执行结果写入节点输出。
20. 视频工厂新增运行前体检与错误中心：运行前检查关键配置，失败或空输出时可集中定位节点。
21. 右侧成片库升级为作品库卡片：支持下载、打开、复用配置和删除记录。
22. 新增模型列表接口：`GET /api/v1/video/workflow/provider-models` 会从 `.env` 的各中转站 baseurl 读取 `/models`，前端可在 GPT / 图片 / Veo 节点下拉切换模型。
23. Veo 与关键帧质量提示增强：首尾帧按真实视频起止帧生成，Veo prompt 强化人物马匹一致性、画面稳定性和“只参考水墨卷轴风格，不照搬旧样片”的约束。
24. 视频提交接口增强：默认兼容 OpenAI 视频格式 `POST /v1/videos`，请求体使用 `model / prompt / size / seconds`；仅在显式设置 `VIDEO_FACTORY_VEO_REQUEST_FORMAT=legacy` 或 `unified` 时才调用旧 `/v1/video/create`。
25. 模型下拉新增常用候选兜底：即使中转站 `/models` 暂时不可用，GPT / 图片 / 视频节点也不会只剩一个模型。
26. 中文配音新增本机兜底：未配置云端 TTS 时，Windows 环境会调用本机中文语音生成旁白，再合成进成片。

## 5. 本次同步文件

1. `README.md`
2. `MANIFEST.md`
3. `视频工厂API填写说明.md`
4. `frontend/workflow-studio/index.html`
5. `frontend/workflow-studio/app.js`
6. `frontend/workflow-studio/styles.css`
7. `backend/app/routers/workflow.py`
8. `backend/app/services/video_factory_providers.py`
9. `backend/app/services/workflow_tasks.py`
10. `config/integration-snippets.md`
11. `backend/data/legendary_horses_top5.json`（已核对为运行环境最新版本）
12. `backend/data/legendary_horses_batch1.json`（已核对为运行环境最新版本）
13. `backend/data/legendary_horses_batch2.json`（已核对为运行环境最新版本）
14. `frontend/horse-rag/index.html`（已核对为最新 RAG 页面）

## 6. 不包含内容

1. 任何真实 API Key / Cookie / Token / `.env`  
2. 生成产物（视频、图片、字幕等）  
3. 目标站点原有业务模块和数据库文件  
