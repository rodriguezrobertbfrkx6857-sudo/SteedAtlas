# 百骑谱 / SteedAtlas V2 — 完整交付包总览

> 解压后请先读本文件。完整细节见 `docs/FINAL_DELIVERY.md`。

- 交付日期：2026-11-01
- 仓库：`baiqipu-github` · 分支 `upgrade/steedatlas-v2`
- HEAD：见 `MANIFEST.json` 的 `head` 字段
- 交付形态：**本地可运行站点 + 真实功能测试 + 原前端视觉对照截图 + 完整验收报告**

---

## 1. 包内容

```
百骑谱V2_完整交付包/
├── README_交付总览.md      ← 本文件
├── MANIFEST.json           ← 每个文件的 sha256 + 字节数 + 分支/commit
├── docs/                   ← 5 份交付文档 + 规范 + RUNBOOK/ROLLBACK/UI 政策
├── reports/                ← 验收证据（A0–A12 + UI0）+ 17 张截图
├── deliverables/           ← 样片 MP4/SRT + 演示清单 + 预览帧
├── runtime/                ← 可运行状态：数据库、旧站备份、媒体、开发密钥
├── scripts/                ← 启动/验收/打包脚本
├── tests/                  ← pytest 套件（49 例）
├── experiments/            ← 实验与消融结果
├── frontend/               ← Vite 工程（默认入口 = 原站黑金界面）
├── wangzhan/               ← 原站源码（含服务端 app/ 与原前端资源）
├── start-v2.ps1            ← 一键启动
├── requirements-dev.txt / pyproject.toml / package-lock.json
└── THIRD_PARTY_NOTICES.md
```

**未包含**（可再生，避免污染包体）：`.venv/`、`frontend/node_modules/`、`*.log`、PID 文件、生产 `.env` 与任何真实凭据。

---

## 2. 三步跑起来

### 第 1 步 — 安装依赖

```powershell
cd 百骑谱V2_完整交付包
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd frontend
npm.cmd ci
cd ..
```

> `npm.cmd ci` 需要网络；无网络时可从本机 npm 缓存离线安装（`npm.cmd ci --offline`）。

### 第 2 步 — 初始化（可选）

包内已含可直接运行的数据库 `runtime/steedatlas.db`（含旧站业务数据 + V2 表），**无需 init**。

若想从空库重建：

```powershell
.\.venv\Scripts\python.exe scripts\run_v2.py init
```

若想导入旧站原始数据备份：

```powershell
.\.venv\Scripts\python.exe scripts\run_v2.py init --import-local-backup
```

### 第 3 步 — 三个终端启动

```powershell
# 终端 1 — API
.\.venv\Scripts\python.exe scripts\run_v2.py api      # http://127.0.0.1:8002

# 终端 2 — Worker（DAG 执行，必须独立运行）
.\.venv\Scripts\python.exe scripts\run_v2.py worker

# 终端 3 — 前端（原站黑金界面）
cd frontend
npm.cmd run dev                                      # http://127.0.0.1:5173
```

或一键启动：`.\start-v2.ps1`（隐藏进程，PID 与日志写入 `runtime/`）。

**打开 http://127.0.0.1:5173 即为原站黑金风格首页。**

---

## 3. 五分钟演示路径

1. 打开 `http://127.0.0.1:5173/` → 确认是**原站黑金风格**（首页、导航、名马图鉴）。
2. 进入「视频工厂」`/workflow-studio/` → 登录 → 填主题 → 提交单条视频任务。
3. 运行日志：`排队中 10% / compose` → `制作中 40% / compose` → **`完成 100% / compose`**。
4. 预览区播放成片（服务端 `206 video/mp4`，HMAC 签名票据）。
5. 点「下载成片」拿到 MP4。

---

## 4. 一键复跑全部验收

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\collect_acceptance_evidence.py
.\.venv\Scripts\python.exe scripts\compat_e2e.py
.\.venv\Scripts\python.exe scripts\live_smoke.py
.\.venv\Scripts\python.exe scripts\browser_qa_original_v2.py
```

---

## 5. 交付自检结论（来自本包解压后的独立验证）

| 检查 | 结果 |
| --- | --- |
| 解压后 `scripts/paths.py` 路径解析 | ROOT / SERVER / alembic.ini / 证据种子全部命中 |
| 解压后启动 API | `/api/v2/capabilities` 200、`/api/v2/agent-providers` 200 |
| 解压后 `npm.cmd ci --offline` | added 109 packages |
| 解压后前端 dev server | `/` 200、`/workflow-studio/` 200，标题「百骑谱 — AI驱动的历史名马数字化商业系统」 |
| 解压后 `pytest tests -q` | **49 passed** |
| 解压后 `scripts/package_original.py` | `Packaged original Baiqipu interface unchanged` |
| 解压后 `scripts/compat_e2e.py` | `ALL COMPAT E2E CHECKS PASSED`（含签名票据、篡改票据 403、下载、SRT、删除后 404） |
| 旧站路由 | `/api/v1/horses` 200、`/api/v2/horses` 200（103 匹名马） |
| 未授权访问 | compat 任务 401 |

---

## 7. 诚实边界（不可视为已完成）

| 项 | 状态 |
| --- | --- |
| 外部大模型 `LIVE_LLM` | **未开通**，调用返回 409 `BLOCKED: LIVE NOT VERIFIED`（不伪造模型记录） |
| 旧 `/generated/*` 历史成片 | 磁盘 0 个文件，**无可认领对象**；审计/认领接口已就绪并测试 |
| 字幕对齐 | 场景级手工时间分布，**非 ASR 精准对齐** |
| 样片音轨 | 合成测试音，**非旁白/非 TTS** |
| GPU / 本地视频模型 / 公网部署 / 付费 API | 未引入、未触发 |

**是否发布由用户决定。** 需要授权的事项集中在 `docs/FINAL_DELIVERY.md` §7.5。
