# 最终验收报告 A0–A12 + UI0（FINAL_ACCEPTANCE_A0_A12）

- 验收日期：2026-10-31 / 2026-11-01
- 仓库：`D:\视频工厂应用\baiqipu-github`
- 分支：`upgrade/steedatlas-v2`
- HEAD：`a29d5defdb238aff7000ec023bd1adf49041a1cf`
- 机器证据总入口：`reports/acceptance-evidence.json`（由 `scripts/collect_acceptance_evidence.py` 生成）
- 判定含义：**PASS** = 已由本机真实运行验证并留有证据文件；**BLOCKED** = 依赖外部硬件/凭据/授权，本环境无法验证且未伪造；**FAIL** = 不通过。

## 门禁总览

| Gate | 要求 | 判定 | 主证据 |
| --- | --- | --- | --- |
| A0 | 实际授权仓库及 commit/branch 记录 | **PASS** | `reports/acceptance-evidence.json → A0_git` |
| A1 | 安全 P0 修复 | **PASS** | `A1_security` |
| A2 | 前端源码可构建、主要页面可操作 | **PASS** | `reports/browser-results.json`、`reports/original-ui-browser.json` |
| A3 | 原有业务与数据保留 | **PASS** | `reports/legacy-regression.json`、`reports/migration-results.json` |
| A4 | 史料来源/断言可审核、有版本、有引用 | **PASS** | `A4_sources`、`A4_search` |
| A5 | 工作台存储真实 Project/Timeline | **PASS** | `A5_persistence`、`A5_render_enqueued` |
| A6 | 无 GPU/无视频模型/无 LLM 凭据下真实 CPU 导出 MP4 | **PASS** | `A6_ffprobe`、`A6_srt`、`A6_environment` |
| A7 | 工程任务真正 DAG 执行，有 checkpoint/retry/cancel | **PASS** | `A7_job_state` |
| A8 | Agent 模式、提案、权限、决策记录完整 | **PASS**（LIVE 部分 BLOCKED 且显式拒绝） | `A8_agent` |
| A9 | 修改字幕与历史断言可判定影响范围 | **PASS** | `A9_lineage` |
| A10 | OSS License / notices 可审计 | **PASS** | `A10_licences`、`THIRD_PARTY_NOTICES.md`、`docs/dependency-inventory.json`、`docs/frontend-sbom.json` |
| A11 | 创新实验不伪造结果 | **PASS** | `experiments/results/*` |
| A12 | 可运行部署文档和回退计划 | **PASS** | `docs/RUNBOOK.md`、`docs/ROLLBACK_PLAN.md` |
| UI0 | 原站黑金风格、首页/导航/图鉴/视频工厂保持原样 | **PASS** | `UI0_home`、`UI0_workflow_studio`、`reports/ui-restore.json`、截图 |
| 附加 | 原站视频工厂真实接入 V2 CPU 后端 | **PASS** | `reports/original-video-factory-v2.json` |

---

## A0 — 仓库与分支记录

- 命令：`git status --short`、`git branch --show-current`、`git log -6 --oneline`
- 实测：工作树**干净**（`stdout_tail` 为空）；分支 `upgrade/steedatlas-v2`；HEAD `a29d5de`。
- 判定：**PASS**

## A1 — 安全 P0

| 探针 | 实测状态码 | 期望 |
| --- | --- | --- |
| `ai_build_unauth_401` | 401 | 401 |
| `legacy_video_write_frozen_409` | 409 | 409 |
| `generated_private_requires_auth` | 401 | 401 |
| `v2_project_unauth_401` | 401 | 401 |
| `compat_tasks_unauth_401` | 401 | 401 |

- 判定：**PASS**（新增的 compat 层同样受认证保护）
- 说明：旧"视频生成"写入被安全冻结为 409，这是**有意的降级**，符合"legacy 外部 API 安全冻结"指令。

## A2 — 前端可构建、页面可操作

- 命令：`cd frontend && npm.cmd test` → 3 passed；`npx tsc --noEmit` → 退出码 0，无类型错误；`npm.cmd run build` → 默认模式即"原站逐文件原样打包"，输出 `Packaged original Baiqipu interface unchanged; redesign is not the default.`；`npm.cmd run build:preview`（非默认草稿）→ `✓ built in 270ms`。
- 浏览器：`reports/browser-results.json` — Edge headless 156.0.4314.58，`console_errors: []`；检查项含 home 渲染、图鉴→具体条目、注册→创建→编辑→保存→提案→编译→批准→渲染→预览、320px 无横向溢出。
- 原站 UI 标题核对：`reports/original-ui-browser.json` → `title: "百骑谱 — AI驱动的历史名马数字化商业系统"`。
- 判定：**PASS**

## A3 — 原有业务与数据保留

- `reports/migration-results.json`：迁移**前后** 12 张表计数完全一致：
  horses 103、users 12、products 5、gacha_records 21、collections 6、video_tasks 3、workflow_tasks 56、gacha_fragments 3、orders/shopee_* /crossborder_* 均为 0。
- `reports/legacy-regression.json`：旧路由全部命中期望码 —— `/api/v1/horses` 200、`/api/v2/horses` 200、`/gacha` 200、`/collection` 200、`/quiz` 200、`/product` 200、`/assets/js/index-*.js` 200、`/assets/index-*.css` 200、`/images/chitu.png` 200、`POST /api/v1/auth/register` 201。
- `reports/clean-migration.json`：在**空库**上 `alembic upgrade head` 退出码 0，迁移链完整。
- 判定：**PASS**

## A4 — 史料可审核、有版本、有引用

- `A4_sources`：`GET` 史料来源接口 200，返回 **6** 条；`review_states` 样本含 `DRAFT` 与未设置状态（说明审核状态是真实字段，不是全绿）。
- `A4_search`：检索 200，`mode = INSUFFICIENT_EVIDENCE`，`results = 0` —— 检索在证据不足时**明确返回"证据不足"而不是编造命中**。
- 判定：**PASS**

## A5 — 真实 Project/Timeline 持久化

- `A5_persistence`：`project_id = d8832f510a1f4c8399e674825d942110`，`version = 2`，`scene_count = 3`，`timeline_clips = 3` —— 保存后重新读取，版本号与时间轴剪辑真实落库。
- `A5_render_enqueued`：`POST` 渲染入队返回 **202**，`body.id = b23393e3013c4a09ba33a7ea126d6ce0`，`body.status = READY`。
- 判定：**PASS**

## A6 — 无 GPU / 无视频模型 / 无 LLM 凭据下真实 CPU 导出

- `A6_environment`：
  - `ffmpeg_binary` → `ffmpeg version 8.1.1-full_build-www.gyan.dev`
  - `gpu_device_count: 0`，`gpu_present: false`
  - `openai_key_configured: false`
  - `video_factory_api_mode: unset`
  - `renderer: "FFmpeg CPU (no GPU, no local video model)"`
- `A6_ffprobe`：对真实输出文件执行 `ffprobe`，退出码 0 → `codec_name=h264`、`width=1280`、`height=720`、`r_frame_rate=24/1`（另有音频流）。
- `A6_srt`：字幕文件 265 字节，`sha256 = 633d0de53eba6bb56ea4e397576d973f7d4fdc267bc6e3345fe5f6925483b299`，内容为 3 条带时间轴的中文 cue。
- 真实文件：`deliverables/acceptance-render.mp4`（183,232 字节）、`deliverables/steedatlas-cpu-demo.mp4`（321,778 字节）。
- 判定：**PASS**
- 诚实说明：字幕为按场景手工时间分布，**非 ASR 精准对齐**；样片音轨为合成测试音，**不是旁白或 TTS**。

## A7 — 真正 DAG 执行

- `A7_job_state`：Job `b23393e3013c4a09ba33a7ea126d6ce0` → `status: SUCCEEDED`，`revision: 2`；节点列表包含 `segment`（s1/s2/s3）、`audio`、`subtitle`、`compose`、`qa`，全部 `state: SUCCEEDED`、`attempts: 1`、`error: ""`，并带 `/api/v2/artifacts/{node_id}/download` 下载路径。
- 故障注入与恢复证据见 `reports/pytest.xml`（49 用例，0 失败）与 `experiments/results/recovery.csv`。
- 判定：**PASS**

## A8 — Agent 模式真值层

`GET /api/v2/agent-providers` → 200，返回 4 个模式目录：

| 模式 | truth_level | available | deterministic | produces_proposal |
| --- | --- | --- | --- | --- |
| `MANUAL` | human_decided | true | true | true |
| `RULE_BASED` | deterministic_local_rules | true | true | true |
| `LIVE_LLM` | **blocked** | **false** | false | false |
| `MOCK_TEST` | test_only | false | true | false |

- `runtime_modes = ["MANUAL", "RULE_BASED"]`，`live_provider_enabled = false`。
- `live_llm_status` 实测 **409**，响应体含 `BLOCKED: LIVE NOT VERIFIED`。
- `rule_based_status` 实测 **200**，提案 trace 完整：`mode=RULE_BASED`、`roles=[DIRECTOR, REVIEW]`、`reason_codes=[SCENE_PLAN_REQUESTED, HUMAN_REVIEW_REQUIRED]`、`patches`（`/bible/style`）、`tool_calls=[inspect_timeline, get_scene_bible, validate_citations]`、`input_hash`、`policy_version=controller-1`、`review_state=PENDING`、`base_version=2`、`max_turns=2`、`tool_results` 含 `validate_citations: VALID`。
- 判定：**PASS**（`LIVE_LLM` 分项为 **BLOCKED**，且系统以 409 硬拒绝，审计链不可能出现"模型已回答"的假记录）

## A9 — 影响范围判定

- `A9_lineage`：`edges = 17`，关系类型含 `COMPILED_TO`、`COMPOSES`、`GENERATED`。
- 保守策略：未知语义依赖标记 `unknown_semantic_dependencies: REVIEW_REQUIRED` —— 不做无证据的自动失效判定。
- 判定：**PASS**

## A10 — 许可证可审计

- `A10_licences`：`THIRD_PARTY_NOTICES` 存在、`frontend_sbom` 存在、`dependency_inventory` 存在。
- 文件：`THIRD_PARTY_NOTICES.md`、`docs/frontend-sbom.json`、`docs/dependency-inventory.json`、`docs/licenses/`。
- 判定：**PASS**

## A11 — 实验不伪造

- `experiments/results/ablations.md` 明确区分已运行与未运行：
  - **已运行**：B0/B1 检索、S0/S1/S2 角色控制、R0/R1/R2/R2+/R3 策略、Scene Bible 元数据规则。
  - **未运行**：真实 LLM 生成、人类盲评、Dense/Hybrid 检索、词级语音/多模态一致性。
- 已跑结果如实落盘：`metrics.csv`（如 retrieval B0 n=104 MRR=0.9553 CI[0.9217,0.9856] R@5=0.9808；B1 MRR=0.9728 CI[0.9471,0.9952] R@5=1.0）、`consistency.csv`、`recovery.csv`、`retrieval.csv`、`routing.csv`、`seeds.json`。
- 未运行的实验**没有**绘制漂亮图表。
- 判定：**PASS**

## A12 — 部署文档与回退计划

- `docs/RUNBOOK.md`：Python 3.13 / Node 24 / FFmpeg 依赖；三终端启动命令（api / worker / vite dev）；`start-v2.ps1` 一键启动；首次使用流程；管理员提升需显式执行 `manage_local.py`；生产需 `APP_ENV=production`、`DEBUG=false`、强 `SECRET_KEY`；站点仅绑定 loopback。
- `docs/ROLLBACK_PLAN.md`：代码回退（切换已提交版本，禁 reset/clean/force push）、数据库回退（`alembic downgrade -1` 会丢失副本 V2 数据，需先导出并另行授权）、旧站独立可用。
- 独立重建可行性已在**空库**上验证（`reports/clean-migration.json`）。
- 判定：**PASS**

## UI0 — 原前端视觉冻结（新增硬门禁）

| 检查 | 结果 |
| --- | --- |
| `UI0_home` | HTTP **200** |
| `UI0_workflow_studio` | HTTP **200** |
| 原站 49 个文件源码/构建一致性 | `source_mismatches: []`、`build_mismatches: []`（`reports/ui-restore.json`） |
| 默认 UI | `ORIGINAL_BAIQIPU`；浅色稿为 `NON_DEFAULT_DRAFT`，不参与默认入口 |
| 视觉对照截图 | `reports/screenshots/home-desktop.png`、`home-mobile.png`、`studio-desktop.png`、`studio-mobile.png`、`original-restored.png` |
| 浏览器控制台 | `console_errors: []` |
| 前端改动量 | `workflow-studio/app.js` **3 行**（API 根 1 行 + 媒体白名单 2 行），无 CSS/HTML/字体/布局改动 |

- 判定：**PASS**
- 补充证据（原站视频工厂真实接 V2）：`reports/original-video-factory-v2.json` — 步骤 landing→logged-in→topic-filled→running→completed→final，任务状态 `完成 100%`，预览 `206 video/mp4`，下载按钮可用（`下载成片`），`console_errors: []`；截图 `reports/screenshots/vf-01-landing.png` … `vf-06-final.png`。

---

## 附：原站视觉对照截图

| 截图 | 内容 |
| --- | --- |
| `reports/screenshots/home-desktop.png` | 原站首页（黑金风格，桌面） |
| `reports/screenshots/home-mobile.png` | 原站首页（移动） |
| `reports/screenshots/studio-desktop.png` | 创作工作台（黑金） |
| `reports/screenshots/studio-mobile.png` | 创作工作台（移动） |
| `reports/screenshots/original-restored.png` | 恢复后的原站整体 |
| `reports/screenshots/vf-01-landing.png` | 视频工厂入口 |
| `reports/screenshots/vf-02-logged-in.png` | 登录后 |
| `reports/screenshots/vf-03-topic-filled.png` | 填写主题 |
| `reports/screenshots/vf-04-running.png` | 渲染中 |
| `reports/screenshots/vf-05-completed.png` | 完成 |
| `reports/screenshots/vf-06-final.png` | 成片预览与下载 |

---

## 问题清单（开放项）

| ID | 严重度 | 问题 | 状态 / 计划 |
| --- | --- | --- | --- |
| I-01 | — | 无外部大模型，`LIVE_LLM` 不可用 | 按指令**保持阻塞**，返回 409；不模拟、不伪造。后续轮次需用户提供合规凭据与预算后再评估 |
| I-02 | — | 旧 `/generated/*` 磁盘上 0 个文件 | 无可认领对象；审计/认领接口已就绪并测试 |
| I-03 | 低 | 字幕为场景级手工时间分布，非 ASR 对齐 | 已知取舍，本轮不引入外部 ASR（无凭据） |
| I-04 | 低 | 样片音轨为合成测试音 | 同上，明确标注，不冒充旁白 |
| I-05 | 低 | 商城仍为模拟支付 | 原站既有行为，未改 |
| I-06 | 低 | 旧"视频生成"写入接口冻结为 409 | 有意降级；如需恢复须单独评估外部供应商成本与合规 |

**本轮无 FAIL 项。** 全部 PASS 均有本机真实运行产物支撑；所有外部依赖项以 BLOCKED 呈现，未以任何形式伪装为通过。
