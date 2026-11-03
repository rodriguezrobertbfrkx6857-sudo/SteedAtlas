# 最终交付说明（FINAL_DELIVERY）

- 交付日期：2026-11-01
- 仓库：`D:\视频工厂应用\baiqipu-github`
- 分支：`upgrade/steedatlas-v2`
- HEAD：`a29d5defdb238aff7000ec023bd1adf49041a1cf`
- 交付形态：**本地可运行站点 + 真实功能测试 + 原前端视觉对照截图 + 完整验收报告**
- 未做：公网部署、付费 API 调用、GPU/模型权重引入、原始数据删除或重置

---

## 1. 快速启动

### 1.1 前置条件

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.13 | 项目内 `.venv` |
| Node.js | 24 | 前端构建与 dev server |
| FFmpeg / FFprobe | 8.1.1 | CPU 视频合成，必须在 PATH |

无 GPU、无模型权重、无付费 API 前置条件。

### 1.2 一次性安装

```powershell
cd D:\视频工厂应用\baiqipu-github
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd frontend
npm.cmd ci
cd ..
.\.venv\Scripts\python.exe scripts\run_v2.py init
```

已有本地备份时，可在 `runtime/steedatlas.db` **尚不存在**的条件下加 `--import-local-backup`；新环境用空库，100 份 JSON 基础图鉴仍可访问，**不伪造历史账户**。

### 1.3 三终端启动

```powershell
# 终端 1 — API
.\.venv\Scripts\python.exe scripts\run_v2.py api      # http://127.0.0.1:8002

# 终端 2 — Worker（DAG 执行，必须独立运行）
.\.venv\Scripts\python.exe scripts\run_v2.py worker

# 终端 3 — 前端（原站黑金界面，Vite dev server）
cd frontend
npm.cmd run dev                                      # http://127.0.0.1:5173
```

或使用一键脚本（端口 8002/5173 空闲时，隐藏进程启动，PID 与日志写入 `runtime/`）：

```powershell
.\start-v2.ps1
```

站点仅绑定 loopback。API 文档：`http://127.0.0.1:8002/docs`

> Worker 未启动时，任务会停在 `READY`/`QUEUED`，前端显示"排队中"而不会假进度。

### 1.4 首次使用

登录/注册 → 图鉴选马 → 创建工程 → 编辑三幕剧本 → 保存 → 上传素材或保留原创模板 → 选择声音/画幅 → 人工审阅 → 导出。

默认新用户为普通创作者。需要本地策展/审核演示时，登录后取本地账户 ID，再显式执行：

```powershell
.\.venv\Scripts\python.exe scripts\manage_local.py --user-id <本地账户ID> --role admin
```

该命令只写审计，不设置默认管理员密码。三个史料示例均为 `DRAFT`，须真人核对原始来源、关系与权利后再批准。

---

## 2. 演示路径（5 分钟走完整个闭环）

### 路径 A：原站视频工厂 → V2 CPU 后端（推荐主演示）

1. 打开 `http://127.0.0.1:5173/`，**确认界面是原站黑金风格**（首页、顶部导航、名马图鉴）。
2. 进入「视频工厂」（`/workflow-studio/`），登录。
3. 填写主题 → 提交单条视频任务。
4. 观察运行日志：任务创建 → `排队中 10% / compose` → `制作中 40% / compose` → **`完成 100% / compose`**。
5. 预览区 `<video>` 播放成片（服务端返回 `206 video/mp4`，走 HMAC 签名票据）。
6. 点击「下载成片」下载 MP4。

> 这条路径与 `reports/original-video-factory-v2.json` 完全对应，截图在 `reports/screenshots/vf-01-landing.png` … `vf-06-final.png`。

### 路径 B：V2 工作台（知识库 / DAG / 时间轴）

1. 选马建工程 → 编辑三幕剧本 → 保存（真实写入 Project + Timeline）。
2. 运行 Agent 提案（`RULE_BASED`）→ 查看提案 trace → 人工批准。
3. 提交渲染 → Worker 执行 `segment → audio → subtitle → compose → qa`。
4. 下载 MP4 + SRT，核对 `ffprobe` 参数。

### 路径 C：一次跑完全部验收

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --junitxml=reports/pytest.xml
.\.venv\Scripts\python.exe scripts\collect_acceptance_evidence.py
.\.venv\Scripts\python.exe scripts\compat_e2e.py
.\.venv\Scripts\python.exe scripts\live_smoke.py
.\.venv\Scripts\python.exe scripts\browser_qa_original_v2.py
```

---

## 3. 样片清单：路径、哈希与媒体参数

### 3.1 验收渲染 `deliverables/acceptance-render.mp4`

| 项 | 值 |
| --- | --- |
| 路径 | `deliverables/acceptance-render.mp4` |
| sha256 | `48A812163CD78C689F4C0029E0EDD34D5CC70D09C068A3DA93469C9DB22E1B76` |
| 大小 | 183,232 字节 |
| 时长 | 6.000000 s |
| 容器 | `mov,mp4,m4a,3gp,3g2,mj2` |
| 视频流 | `h264` / `Constrained Baseline` / `1280x720` / `yuv420p` / `24/1` fps |
| 总码率 | 244,309 bps |

配套字幕 `deliverables/acceptance-render.srt`：
- 大小 265 字节，sha256 `633D0DE53EBA6BB56EA4E397576D973F7D4FDC267BC6E3345FE5F6925483B299`
- 3 条 cue，例：`00:00:00,000 --> 00:00:02,000` / `[CREATIVE] 第1幕：循着记载，认识名马。`

### 3.2 完整演示样片 `deliverables/steedatlas-cpu-demo.mp4`

| 项 | 值 |
| --- | --- |
| 路径 | `deliverables/steedatlas-cpu-demo.mp4` |
| sha256 | `9E9D532E6AF3B8E5DC260A904BE2035A923BC8FCFC2C609D043E24EB0F24B1CD` |
| 大小 | 321,778 字节 |
| 时长 | 9.000000 s |
| 视频流 | `h264` / `1280x720` / `24/1` fps |
| 音频流 | `aac` / 48000 Hz / 1 声道（**合成测试音，非旁白、非 TTS**） |
| 总码率 | 286,024 bps |
| decoded | true（`deliverables/demo-manifest.json → probe`） |

配套字幕 `deliverables/steedatlas-cpu-demo.srt`：313 字节，sha256 `50E0E9B41262D331BC0432048B0E332F86206174929A082E4DCFD407E38657B6`

### 3.3 演示清单 `deliverables/demo-manifest.json`

```json
{
  "mode": "REAL_CPU_FFMPEG_NO_MODEL",
  "audio": "Synthetic test tone, not speech or TTS",
  "assets": [
    {"id": "68d89d94987a4467ad6df9565aec0000", "sha256": "56e578c781022e3fb3d6f805206db32e728e147a8cc2893ed8c8a8b59780054f", "license": "Original programmatic illustration"},
    {"id": "e006059fc8074f78ac0fdcf4a559c0d5", "sha256": "f6f74ef4db6439aa44899ea828ed2a531831fa0c7cd77cb7407ddd9d9db0eb95", "license": "Original programmatic illustration"},
    {"id": "860ec85188a34847ac774d3257212f6e", "sha256": "659d995182b91003c4ce6186acb6375224c32ae261e57ffe3ab65f5ca92c19c2", "license": "Original programmatic illustration"},
    {"id": "1813729ad7c34a07b3e50001ca67f272", "sha256": "3b52a4301611bf62a847ab6166784275b4a63b6e916fed00850622c5c796bb5f", "license": "Synthetic test tone; not narration"}
  ],
  "job": {"status": "SUCCEEDED", "revision": 3, "nodes": ["segment s1/s2/s3", "audio", "subtitle", "compose", "qa"]},
  "events": ["ENQUEUED", "LEASED", "SUCCEEDED", ...],
  "trace": {"mode": "RULE_BASED", "roles": ["DIRECTOR","REVIEW"], "review_state": "PENDING"},
  "probe": {"sha256": "9e9d...", "bytes": 321778, "duration": 9.0, "width": 1280, "height": 720, "fps": "24/1", "decoded": true}
}
```

三幅画面素材为**程序化原创几何插画**（非历史图像再创作），许可记录在清单内。

---

## 4. 交付物清单

### 4.1 文档

| 文件 | 内容 |
| --- | --- |
| `docs/RESUME_AUDIT.md` | 接管起点、Git 状态、变更分类、已验证/未验证成果 |
| `docs/LEGACY_V2_INTEGRATION.md` | 原页面→V2 API 映射、改动文件、黑金 UI 保留措施、回滚方法 |
| `docs/FINAL_ACCEPTANCE_A0_A12.md` | A0–A12 + UI0 逐条 PASS/FAIL/BLOCKED 与证据 |
| `docs/AGENT_MODE_TRUTH.md` | MANUAL / RULE_BASED / LIVE_LLM / MOCK_TEST 真实能力边界 |
| `docs/FINAL_DELIVERY.md` | 本文件 |
| `docs/RUNBOOK.md` | 本地开发与复现手册 |
| `docs/ROLLBACK_PLAN.md` | 代码与数据库回退 |
| `docs/UI_CHANGE_POLICY.md` | 界面范围冻结政策 |
| `THIRD_PARTY_NOTICES.md` | 第三方许可声明 |

### 4.2 机器证据（`reports/`）

| 文件 | 内容 |
| --- | --- |
| `acceptance-evidence.json` | A0–A12 + UI0 全部探针结果 |
| `pytest.xml` | 49 用例，errors=0 failures=0 |
| `browser-results.json` | 真实浏览器（Edge 156）交互与性能 |
| `original-ui-browser.json` | 原站 UI 标题与控制台 |
| `original-video-factory-v2.json` | 原站视频工厂接入 V2 的端到端结果 |
| `ui-restore.json` | 原站 49 文件源码/构建一致性 |
| `legacy-regression.json` | 旧路由回归 |
| `migration-results.json` | 迁移前后表计数对比 + downgrade 验证 |
| `clean-migration.json` | 空库全新迁移 |
| `legacy-asset-ownership.json` | 旧 `/generated/*` 所有权审计 |
| `runtime-poc.json` | 任务队列选型 POC |
| `instruction-integrity.json` | 规范文件完整性校验 |
| `screenshots/*.png` | 视觉对照与流程截图 |

### 4.3 代码改动（全部已提交）

- 后端新增：`app/v2/compat.py`、`app/v2/legacy_assets.py`、`app/v2/agent_providers.py`
- 后端修改：`app/v2/security.py`（HMAC 票据）、`app/v2/contracts.py`（1080×1080）、`app/v2/api.py`、`app/main.py`
- 前端修改：**仅** `workflow-studio/app.js` 3 行（API 根 1 行 + 媒体白名单 2 行）
- 测试新增：`tests/test_compat_video_factory.py`（14）、`tests/test_agent_providers.py`（7）
- 脚本新增：`compat_e2e.py`、`live_smoke.py`、`browser_qa_original_v2.py`、`audit_legacy_assets.py`、`collect_acceptance_evidence.py`

### 4.4 测试结果汇总

| 命令 | 结果 |
| --- | --- |
| `pytest tests -q` | **49 passed in 63.67s** |
| `npm.cmd test` | 3 passed |
| `npx tsc --noEmit` | 无错误（退出码 0） |
| `npm.cmd run build` | 默认模式 = **原站逐文件原样打包**，输出 `Packaged original Baiqipu interface unchanged; redesign is not the default.` |
| `npm.cmd run build:preview` | `tsc --noEmit && vite build --mode redesign` → `✓ built in 270ms`（仅非默认草稿） |
| `scripts/collect_acceptance_evidence.py` | A0–A12 + UI0 全部采集成功 |
| `scripts/browser_qa_original_v2.py` | `console_errors: []`，`完成 100%` |
| `scripts/live_smoke.py` | 真实 MP4/SRT 生成 |
| `scripts/compat_e2e.py` | 兼容契约全通 |

---

## 5. 原前端视觉对照（黑金风格保留）

| 截图 | 说明 |
| --- | --- |
| `reports/screenshots/home-desktop.png` | 原站首页（桌面，黑金） |
| `reports/screenshots/home-mobile.png` | 原站首页（移动） |
| `reports/screenshots/studio-desktop.png` | 创作工作台（桌面） |
| `reports/screenshots/studio-mobile.png` | 创作工作台（移动） |
| `reports/screenshots/original-restored.png` | 原站整体恢复后 |
| `reports/screenshots/initial.png` / `after-reload.png` / `passage.png` / `export.png` | 图鉴条目与导出流程 |
| `reports/screenshots/vf-01..vf-06` | 视频工厂 6 步流程 |

核验：`reports/ui-restore.json` → 49 个原文件，`source_mismatches: []`、`build_mismatches: []`，`default_ui: ORIGINAL_BAIQIPU`；新浅色稿保持 `NON_DEFAULT_DRAFT`，不进默认入口。320px 无横向溢出。

**本轮前端没有发生任何视觉改动**，只有 3 行 API 接线。

---

## 6. 遗留问题（按优先级）

| ID | 优先级 | 问题 | 影响 | 处置 |
| --- | --- | --- | --- | --- |
| I-01 | P2 | 无外部大模型，`LIVE_LLM` 不可用 | Agent 无法做开放式创作决策 | **保持阻塞**，调用返回 409 `BLOCKED: LIVE NOT VERIFIED`；开通条件见 `AGENT_MODE_TRUTH.md` 第 7 节 |
| I-02 | P2 | 旧 `/generated/*` 磁盘 0 文件 | 历史成片无法逐个认领 | 无对象即无可认领；审计/认领接口已就绪并测试 |
| I-03 | P3 | 字幕为场景级手工时间分布，非 ASR 对齐 | 字幕与语音可能不完全贴合 | 已知取舍；引入 ASR 需外部凭据与费用授权 |
| I-04 | P3 | 样片音轨为合成测试音 | 样片无真实旁白 | 同上；清单与本文均已显式标注 |
| I-05 | P3 | 商城仍为模拟支付 | 无法真实交易 | 原站既有行为，未改 |
| I-06 | P3 | 旧「视频生成」写入接口冻结为 409 | 旧生成器不可用 | 有意降级；恢复需评估外部供应商成本与合规 |
| I-07 | P3 | 未跑真实 LLM 生成、人类盲评、Dense/Hybrid 检索 | 实验结论覆盖面有限 | `experiments/results/ablations.md` 已如实标注未运行项 |

**无 P0/P1 遗留项。** 全部遗留均为外部依赖或有意取舍，未以任何形式伪装为已完成。

---

## 7. 下一轮建议

### 7.1 优先级 1 —— 补齐可验证的 Agent 能力（需用户授权）

1. 用户提供合规外部模型凭据 + 明确预算上限。
2. 实现真正的 provider 适配器（超时/重试/错误映射），把 `LIVE_LLM` 的 `available` 改为 `true` 并补齐成功/失败/超时测试。
3. 保持"所有提案需人工批准"的硬约束不变。

### 7.2 优先级 2 —— 音画对齐质量

1. 引入本地可离线运行的 ASR/对齐方案（若可获得授权权重），把字幕时间轴从"按场景手工分配"升级为"按语音对齐"。
2. 改进旁白：区分"合成测试音"与"语音旁白"两条独立产物线，验收报告分别记录。

### 7.3 优先级 3 —— 数据与素材

1. 若后续导入真实历史成片到 `/generated/`，先跑 `scripts/audit_legacy_assets.py` 生成归属报告，再由 staff 逐条执行认领；禁止批量无审计导入。
2. 抽样对 3 份史料示例做人工审稿，把 `review_states` 从 `DRAFT` 推进到 `APPROVED`，形成可展示的审核链。

### 7.4 优先级 4 —— 工程化

1. 补齐 DAG 故障注入矩阵（每种节点各一次失败）与自动恢复证据。
2. 把 `collect_acceptance_evidence.py` 接入 CI（GitHub Actions 现仅 `workflow_dispatch`，未触发过云端 CI）。
3. 明确部署形态与对外访问的安全方案（当前仅 loopback）。

### 7.5 需要用户后续授权的事项（集中列出）

| 事项 | 类型 |
| --- | --- |
| 外部大模型 API 凭据与预算 | 付费调用授权 |
| GPU/模型权重下载 | 范围外资源获取 |
| 公网部署与域名 | 公开部署授权 |
| 生产库 `alembic downgrade` 回退 | 不可逆数据操作 |
| 真实历史成片批量导入 `/generated/` | 数据写入授权 |

---

## 8. 复现与独立重建

本交付可由另一位开发者在独立工作区复现：

```powershell
git clone <repo> && cd baiqipu-github
git checkout upgrade/steedatlas-v2
# 按 §1.2 安装，§1.3 启动
# 按 §2.3 跑全部验收脚本
```

独立重建可行性已在**空库**上验证（`reports/clean-migration.json`，`alembic upgrade head` 退出码 0）。原始数据库与原站目录**未被本轮改动**。

**最终是否发布由用户决定。**
