# 原站「视频工厂」→ V2 后端集成说明（LEGACY_V2_INTEGRATION）

本文件描述原百骑谱站的视频工厂页面如何被接入 V2 CPU DAG 渲染后端，包含契约映射、改动文件清单、黑金 UI 保留措施与回滚方法。

**核心原则：原站前端不改版。** 集成全部在服务端通过"兼容适配器"完成，前端只改了 API 根路径一行与媒体白名单两行。

---

## 1. 集成方式：兼容适配器（ADR）

原站 `workflow-studio/app.js` 期望的是 V1 契约（`WorkflowTaskCreateIn` / `WorkflowTaskOut`）。V2 后端的数据模型完全不同（`CreativeProject` / `Job` / DAG `Node`）。因此**不修改 V2 模型去迁就旧契约**，而是新增一个 V2 之上的适配器：

```
原站 workflow-studio/app.js
        │  仍是 V1 契约的 JSON
        ▼
/api/v2/compat/workflow  ← app/v2/compat.py（本轮新增）
        │  翻译
        ▼
V2: CreativeProject(kind=project) + Job + Node
        │  Worker 执行
        ▼
DAG 节点：segment → audio → subtitle → compose → qa
        │  FFmpeg CPU
        ▼
真实 MP4 / SRT
```

适配器挂载在 `app/main.py`，与 V2 其它路由并列；`/api/v1` 原业务路由完全不受影响。

---

## 2. 接口映射表

| 原站前端调用（旧） | 适配器端点（新） | V2 内部实现 | 说明 |
| --- | --- | --- | --- |
| `GET {base}/provider-status` | `GET /api/v2/compat/workflow/provider-status` | 读取 `app/v2/runtime.py` 与本机 FFmpeg 探测 | 返回给原站的 provider 列表与 `mediaBaseUrl`；外部模型一律标记不可用 |
| `GET {base}/provider-models` | `GET /api/v2/compat/workflow/provider-models` | 静态目录 | 站内 CPU 渲染可用；外部模型条目 `blocked` |
| `POST {base}/reference/upload` | `POST /api/v2/compat/workflow/reference/upload` | V2 资产表 + 私有存储 | 与原站 multipart 字段名兼容；`db` 由依赖注入，便于测试覆盖 |
| `POST {base}/tasks` | `POST /api/v2/compat/workflow/tasks` | 建 `Entity(kind=project)` + `Job` | 保留旧字段 `workflow_definition`；写任务进度供原站进度条读取 |
| `GET {base}/tasks` | `GET /api/v2/compat/workflow/tasks` | 列举本人任务 | 旧 `task_id` ↔ V2 `Entity.id` |
| `GET {base}/tasks/{id}` | `GET /api/v2/compat/workflow/tasks/{id}` | `_serialize_task` | 复用旧字段名（`task_id`/`status`/`progress`/`created_at`/`result`） |
| `POST {base}/tasks/{id}/run` | `POST /api/v2/compat/workflow/tasks/{id}/run` | `_enqueue_render` → DAG | 幂等：已有运行中 Job 直接返回 |
| `GET {base}/tasks/{id}/runtime` | `GET /api/v2/compat/workflow/tasks/{id}/runtime` | 节点状态快照 | 供原站运行日志显示 `segment/audio/subtitle/compose/qa` |
| `GET {base}/tasks/{id}/download` | `GET /api/v2/compat/workflow/tasks/{id}/download` | 读取合成产物 | 旧前端只需一个可下载 URL |
| `POST {base}/tasks/{id}/clear` | `POST /api/v2/compat/workflow/tasks/{id}/clear` | 清空结果与产物引用 | — |
| `DELETE {base}/tasks/{id}` | `DELETE /api/v2/compat/workflow/tasks/{id}` | 软删除 | — |
| `DELETE {base}/tasks` | `DELETE /api/v2/compat/workflow/tasks` | 批量清理本人任务 | — |
| （新增） | `GET /api/v2/compat/workflow/media/{identity}` | 私有产物流式播放 | 见第 3 节 |

节点顺序固定为原站画布顺序：`segment → audio → subtitle → compose → qa`，见 `app/v2/compat.py` 顶部常量。

---

## 3. HMAC 签名媒体票据（解决 `<video src>` 不能带 Bearer 的矛盾）

浏览器 `<video src>` 无法附加 `Authorization` 头，但产物必须保持私有 ACL。解法是服务端签发短期票据：

```python
# app/v2/security.py
def issue_media_ticket(identity: str, owner: str, ttl_seconds: int = 3600) -> str
def verify_media_ticket(identity: str, owner: str, ticket: str) -> bool
```

票据签名内容为 `(node_id, owner, expiry)`，用 HMAC-SHA256 与服务端密钥计算。

- 播放 URL 形如 `/api/v2/compat/workflow/media/node-15e0032f...?...ticket`
- 服务端仍按 `owner` 校验 ACL，票据只是"短期免头凭据"，不改变所有权模型
- TTL 1 小时，过期即失效

前端仅需把该前缀加入 `safeMediaUrl` 白名单（原站已有 `/generated/` 等白名单逻辑），**不需要改动任何 DOM 结构或样式**。

实测：`GET /api/v2/compat/workflow/media/node-...` 返回 `206 video/mp4`（见 `reports/original-video-factory-v2.json`）。

---

## 4. 改动文件清单（前端只有 3 行）

### 后端

| 文件 | 状态 | 改动摘要 |
| --- | --- | --- |
| `wangzhan/{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server/app/v2/compat.py` | 新增 | 兼容适配器，13 个端点 |
| `.../app/v2/legacy_assets.py` | 新增 | 旧素材审计 / 认领 / 清单 |
| `.../app/v2/agent_providers.py` | 新增 | Agent 模式真值注册表 |
| `.../app/v2/security.py` | 修改 | +38 行 HMAC 票据函数 |
| `.../app/v2/contracts.py` | 修改 | +8 行：分辨率白名单加 `(1080, 1080)` |
| `.../app/v2/api.py` | 修改 | `/capabilities` 增加 agent 信息；接入 agent 守卫 |
| `.../app/main.py` | 修改 | +4 行：挂载两个新路由 |

### 前端（原站文件）

| 文件 | 改动行数 | 内容 |
| --- | --- | --- |
| `wangzhan/baiqipu.com-source-20260424-194149/workflow-studio/app.js` | **3 行**（1 改 + 2 增） | `WORKFLOW_API_BASE` 指向 `/api/v2/compat/workflow`；`safeMediaUrl` 放行 `/api/v2/compat/workflow/media/` |

**没有任何** CSS、HTML、模板、字体、配色、布局、导航、动画文件被修改。

---

## 5. 黑金 UI 保留措施（可核验）

| 措施 | 核验方式 | 结果 |
| --- | --- | --- |
| 原站 49 个资源文件逐文件比对源码与构建产物 | `scripts/package_original.py` → `reports/ui-restore.json` | `source_mismatches: []`、`build_mismatches: []` |
| 默认入口仍指向原站目录 | `frontend/vite.config.ts` 代理 `/workflow-studio/` → 原站目录 | PASS |
| 新浅色设计稿保持"非默认草稿"，不参与默认入口 | `reports/ui-restore.json` → `default_ui: ORIGINAL_BAIQIPU`、`redesign: NON_DEFAULT_DRAFT` | PASS |
| 视觉对照截图 | `reports/screenshots/home-desktop.png`、`home-mobile.png`、`studio-desktop.png`、`studio-mobile.png`、`original-restored.png` | PASS |
| 浏览器实测标题与控制台 | `reports/original-ui-browser.json`：title 为「百骑谱 — AI驱动的历史名马数字化商业系统」，`console_errors: []` | PASS |
| 320px 无横向溢出 | `reports/browser-results.json` | PASS |

---

## 6. 权限与安全边界

| 场景 | 行为 |
| --- | --- |
| 未登录访问 compat 任意端点 | `401`（`A1_security.compat_tasks_unauth_401 = 401`） |
| 访问他人任务 | `404`（不泄露存在性） |
| 访问他人产物 | `404` |
| 媒体票据过期/篡改 | `404` |
| 原站旧"视频生成"写入接口 | `409` 冻结（`legacy_video_write_frozen_409`） |
| `/generated/*` 私有目录直连 | `401`（`generated_private_requires_auth`） |
| 旧素材认领 | 仅 staff 可审计；认领需登录且必须能由 `workflow_tasks.user_id` 证明归属；路径穿越一律拒绝 |

---

## 7. 回滚方法

### 7.1 只回滚本次集成（推荐）

```powershell
cd D:\视频工厂应用\baiqipu-github
git log --oneline -3
git revert --no-commit 32e3ea6 a29d5de
# 如需同时恢复前端旧 API 根路径，确认 diff 后提交
git commit -m "revert: undo video factory V2 compat integration"
```

回滚后原站 `app.js` 的 `WORKFLOW_API_BASE` 回到 `/api/v1/video/workflow`，旧视频生成接口本身仍处冻结态（409），需要时才另行解冻。

### 7.2 完全回退到受保护基线

```powershell
git checkout 162a28575d957e1248b7fa1f7380c68e30dd5ad1 -- <目标路径>
```

**禁止** `git reset --hard`、`git clean -fd`、`git push --force` —— 会丢失未提交成果。

### 7.3 数据库回退

V2 采用**新增表**（expand-only），回退用：

```powershell
.\.venv\Scripts\python.exe scripts\run_v2.py db downgrade -1
```

会删除 V2 表并**丢失该副本的 V2 项目数据**，操作前必须先导出。真实环境需额外授权。本次交付**未执行**生产回退；回退验证只在副本上进行，见 `reports/migration-results.json`（`downgrade a8d4e7f9c201` 退出码 0，且迁移前后旧表计数一致）。

### 7.4 旧站完全独立可用

原站目录 `wangzhan/` 与原始数据库未改动，仍可用 `wangzhan/start-site.bat` 独立运行。

---

## 8. 复现验证

```powershell
# 适配器端到端（无需浏览器）
.\.venv\Scripts\python.exe scripts\compat_e2e.py

# 真实本地 CPU 冒烟
.\.venv\Scripts\python.exe scripts\live_smoke.py

# 原站前端在真实浏览器里跑通 V2 后端
.\.venv\Scripts\python.exe scripts\browser_qa_original_v2.py
```

三者的产物分别写入 `reports/original-video-factory-v2.json`、`deliverables/` 与 `reports/screenshots/vf-0*.png`。
