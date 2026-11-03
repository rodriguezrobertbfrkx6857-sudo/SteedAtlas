# 集成代码片段

这些片段不是完整文件，只是把视频工厂接入目标网站时通常要合并的位置。

## 1. config.py 增加字段

目标网站如果使用 `pydantic-settings` 或类似配置类，请把下面字段合并进去：

```python
REDIS_URL: str = "redis://localhost:6379/0"
WORKFLOW_RUNTIME_REDIS_ENABLED: bool = True
WORKFLOW_RUNTIME_REDIS_PREFIX: str = "baiqipu:workflow:task:"
WORKFLOW_RUNTIME_REDIS_TTL_SECONDS: int = 86400
WORKFLOW_RUNTIME_REDIS_EVENT_LIMIT: int = 120

VIDEO_FACTORY_API_MODE: str = "auto"
VIDEO_FACTORY_MEDIA_BASE_URL: str = "/generated"
VIDEO_FACTORY_DOWNLOAD_REMOTE_MEDIA: bool = False
VIDEO_FACTORY_TEMPLATE_STORAGE_DIR: str = "./storage/template_versions"
AZURE_TTS_KEY: str = ""
AZURE_TTS_REGION: str = ""
VIDEO_FACTORY_GPT_API_KEY: str = ""
VIDEO_FACTORY_GPT_BASE_URL: str = ""
VIDEO_FACTORY_GPT_MODEL: str = ""
VIDEO_FACTORY_GPT_API_PATH: str = "/chat/completions"
VIDEO_FACTORY_GPT_API_STYLE: str = "chat_completions"
VIDEO_FACTORY_GPT_MAX_TOKENS: int = 1800
VIDEO_FACTORY_GPT_TIMEOUT_SECONDS: float = 60.0
VIDEO_FACTORY_IMAGE_API_KEY: str = ""
VIDEO_FACTORY_IMAGE_BASE_URL: str = ""
VIDEO_FACTORY_IMAGE_MODEL: str = "gpt-image-2"
VIDEO_FACTORY_IMAGE_API_PATH: str = "/images/generations"
VIDEO_FACTORY_IMAGE_SIZE: str = "1024x1792"
VIDEO_FACTORY_IMAGE_TIMEOUT_SECONDS: float = 120.0
VIDEO_FACTORY_VEO_API_KEY: str = ""
VIDEO_FACTORY_VEO_BASE_URL: str = ""
VIDEO_FACTORY_VEO_MODEL: str = "veo-3.0-generate-001"
VIDEO_FACTORY_VEO_API_PATH: str = "/videos/generations"
VIDEO_FACTORY_VEO_STATUS_API_PATH: str = ""
VIDEO_FACTORY_VEO_REQUEST_FORMAT: str = "json"
VIDEO_FACTORY_VEO_TIMEOUT_SECONDS: float = 180.0
VIDEO_FACTORY_VEO_GENERATE_AUDIO: bool = True
VIDEO_FACTORY_VEO_ENHANCE_PROMPT: bool = True
VIDEO_FACTORY_VEO_MAX_CLIPS_PER_TASK: int = 1
VIDEO_FACTORY_VEO_WAIT_FOR_COMPLETION: bool = True
VIDEO_FACTORY_VEO_POLL_INTERVAL_SECONDS: float = 15.0
VIDEO_FACTORY_VEO_MAX_POLL_ATTEMPTS: int = 60
XHS_AUTOPUBLISH_ENABLED: bool = False
XHS_MCP_BASE_URL: str = "http://127.0.0.1:18060"
XHS_MCP_PUBLISH_VIDEO_PATH: str = "/api/v1/publish_video"
XHS_MCP_TIMEOUT_SECONDS: float = 180.0
XHS_COOKIE_PATH: str = ""
XHS_DEFAULT_VISIBILITY: str = "公开可见"
BAIQIPU_FFMPEG_BIN: str = "ffmpeg"
```

## 2. main.py 注册路由和输出目录

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.routers import workflow, horses

app.include_router(workflow.router, prefix="/api/v1")
app.include_router(horses.router, prefix="/api/v1")

server_dir = Path(__file__).resolve().parents[1]
generated_dir = server_dir / "generated"
generated_dir.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=generated_dir), name="generated")
```

## 3. 数据库模型

把 `backend/app/models/workflow_task.py` 放进目标后端后，要确保应用启动或迁移时会创建 `workflow_tasks` 表。

如果目标项目使用 `Base.metadata.create_all(...)`，要让 `WorkflowTask` 模型在 create_all 前被 import。

如果目标项目使用 Alembic，请为 `workflow_tasks` 表生成一次迁移。

## 4. 前端静态路由

把 `frontend/workflow-studio/` 放到目标网站静态目录后，推荐访问路径保持：

```text
/workflow-studio/
```

把 `frontend/horse-rag/` 放到目标网站静态目录后，推荐访问路径保持：

```text
/horse-rag/
```

把 `frontend/images/` 放到目标网站静态目录的同级 `images/` 目录，供视频工厂和 RAG 页面作为默认预览图。

前端默认请求：

```text
/api/v1/video/workflow
```

如果目标网站 API 前缀不同，修改 `frontend/workflow-studio/app.js` 顶部：

```js
const WORKFLOW_API_BASE = "/api/v1/video/workflow";
const HORSE_RAG_API = "/api/v1/horses/rag-library";
```

如果登录 token 的 localStorage 名称不同，修改：

```js
const AUTH_STORAGE_KEY = "auth-storage";
```

## 4.1 RAG 马库接口与数据文件

后端路由文件：

```text
backend/app/routers/horses.py
```

后端数据文件：

```text
backend/data/legendary_horses_top5.json
backend/data/legendary_horses_batch1.json
backend/data/legendary_horses_batch2.json
```

接口：

```text
GET /api/v1/horses/rag-library?size=200
GET /api/v1/horses/rag-library/{horse_id}
GET /api/v1/horses/rag-library/stats
```

最小验证：

```bash
curl "http://127.0.0.1:8000/api/v1/horses/rag-library?size=200"
```

正常返回应包含：

```json
{"total": 100, "items": ["..."]}
```

同步与缓存说明：

1. 本包的三份数据文件合计 100 匹名马，`story`、`horse_life_story`、`owner_life_story` 已按加长版同步。
2. `rag-library` 接口按当前 `backend/data/legendary_horses_top5.json` 与 `legendary_horses_batch*.json` 读取并合并返回，不依赖旧数据缓存。
3. 替换数据文件后，重新请求 `GET /api/v1/horses/rag-library?size=200` 验证；正常应返回 `total=100`，详情接口应能读到扩写后的“马的一生”和“主人的一生”。
4. `/horse-rag/` 页面已同步最新排版修复：详情区图片与文本分栏固定，移动端单列展示，长文不会覆盖图片或标题。

## 4.1 模型列表接口（前端模型下拉）

后端路由（已在 `backend/app/routers/workflow.py`）：

```text
GET /api/v1/video/workflow/provider-models
```

用途：

1. 从 `.env` 的 GPT / 图片 / Veo / ASR `*_BASE_URL` 读取中转站 `/models`。
2. 返回模型名、默认模型、质量/速度提示，不返回 API Key。
3. 前端 `workflow-studio/app.js` 会把返回值填入“模型选择”下拉框。

最小验证：

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/video/workflow/provider-models" \
  -H "Authorization: Bearer <token>"
```

如果中转站不支持 `/models`，接口会保留 `.env` 默认模型并返回错误摘要；生成流程仍可继续。

## 5. 模板系统版本化接口（保存 / 应用 / 删除）

后端路由（已在 `backend/app/routers/workflow.py`）：

```text
GET    /api/v1/video/workflow/templates/versions
POST   /api/v1/video/workflow/templates/versions
GET    /api/v1/video/workflow/templates/versions/{template_id}
DELETE /api/v1/video/workflow/templates/versions/{template_id}
```

### 5.1 保存模板版本（示例）

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/video/workflow/templates/versions" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "templateId": "warhorse-hq",
    "name": "战马高质量模板",
    "description": "3分镜长视频，连续性优先",
    "tags": ["国风", "战场", "长视频"],
    "shotTemplate": "3镜头，每镜8秒，起承转合",
    "keyframeStrategy": "首尾关键帧 + 分镜衔接",
    "veoPrompt": "电影级光影，镜头稳定，角色一致",
    "veoNegativePrompt": "避免现代元素、避免卡通风",
    "notes": "v3：强化尾帧到次镜首帧连续性",
    "extraConfig": {"runMode": "final-quality"}
  }'
```

### 5.2 读取模板版本列表（示例）

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/video/workflow/templates/versions" \
  -H "Authorization: Bearer <token>"
```

### 5.3 删除模板版本组（示例）

```bash
curl -X DELETE "http://127.0.0.1:8000/api/v1/video/workflow/templates/versions/warhorse-hq" \
  -H "Authorization: Bearer <token>"
```

> 说明：删除按 `templateId` 整组删除，该模板下全部版本会被移除。

## 6. 小红书节点产品化接口（连接测试 / Cookie 健康）

后端路由：

```text
POST /api/v1/video/workflow/xhs/test-connection
POST /api/v1/video/workflow/xhs/cookie-health
```

### 6.1 连接测试（示例）

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/video/workflow/xhs/test-connection" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "baseUrl": "http://127.0.0.1:18060",
    "publishPath": "/api/v1/publish_video",
    "timeoutSeconds": 8,
    "method": "OPTIONS"
  }'
```

### 6.2 Cookie 有效期检测（示例）

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/video/workflow/xhs/cookie-health" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cookiePath": "D:\\\\xhs\\\\cookies.json",
    "warningHours": 72
  }'
```

返回重点字段：

- `valid`: 是否结构可解析
- `expired`: 是否已过期
- `expiringSoon`: 是否接近过期
- `remainingHours`: 剩余小时数
- `notes`: 诊断提示

## 7. 发布策略配置建议（草稿 / 定时 / 失败回滚）

1. 草稿发布：`visibility=仅自己可见`，先跑通链路再改公开。
2. 定时发布：
   - 优先让 MCP 发布接口支持 `scheduledAt`；
   - 若发布端不支持，就用系统定时任务在目标时间触发工作流。
3. 失败回滚：
   - 失败时只回滚“发布动作”，不删除已生成成片；
   - 记录失败节点输出（`endpoint`、`response`、`error`），修复后重试发布。

## 8. 常见故障定位（模板 + 小红书）

1. 模板保存失败（400）
   - 检查 `shotTemplate/keyframeStrategy/veoPrompt` 是否全部为空。
2. 模板列表为空
   - 检查登录态与 token；确认调用账号和保存账号一致。
3. 小红书连接测试失败
   - 检查 `baseUrl + publishPath` 拼接后的地址是否可访问。
4. Cookie 检测失败
   - 检查 `cookiePath` 是否为服务器可读绝对路径。
5. 自动发布被跳过
   - 检查节点 `enabled`、`cookiePath`、以及是否已有本地成片文件。
