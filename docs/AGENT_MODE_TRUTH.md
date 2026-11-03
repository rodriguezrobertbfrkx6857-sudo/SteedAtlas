# Agent 模式真值边界（AGENT_MODE_TRUTH）

本文件说明 V2 Agent 系统中每个模式**实际能做什么、不能做什么**，避免任何记录暗示"模型回答了"而实际并未发生。

实现位置：`app/v2/agent_providers.py`（注册表与真值描述）
对外目录：`GET /api/v2/agent-providers`
运行模式白名单：`RUNTIME_MODES = ("MANUAL", "RULE_BASED")`

---

## 1. 一句话总览

> **本环境未接入任何外部大模型。** 站内只有两种可用模式：`MANUAL`（人工决策）与 `RULE_BASED`（站内确定性规则引擎）。`LIVE_LLM` 是保留骨架，任何调用都被拒绝并返回 `BLOCKED: LIVE NOT VERIFIED`（HTTP 409）。`MOCK_TEST` 仅供自动化测试使用。

---

## 2. 四个模式的真实能力

### 2.1 `MANUAL` — 人工决策

| 维度 | 事实 |
| --- | --- |
| truth_level | `human_decided` |
| available | **true**（可选用） |
| deterministic | true（同样输入产出同样的记录） |
| produces_proposal | true（产生的是"提案壳"，不含自动补丁） |
| requires_approval | true |
| 是否调用模型 | **否** |
| 实际行为 | 人决定每一处改动；Agent 只负责**记录决定与理由**，写入提案/审计记录 |

- 提案内容里 `patches` 为空数组；`reason_codes` 记录人的决策原因。
- 记录里的 `mode` 字段是 `MANUAL`，不会与模型产出混淆。
- 边界：**Agent 不能代替人批准**。批准动作永远需要人工授权上下文。

### 2.2 `RULE_BASED` — 站内确定性规则引擎

| 维度 | 事实 |
| --- | --- |
| truth_level | `deterministic_local_rules` |
| available | **true**（可选用） |
| deterministic | true（同一工程版本 → 同一提案） |
| produces_proposal | true |
| requires_approval | true |
| 是否调用模型 | **否**（纯本地规则，无网络请求、无凭据） |
| 实际行为 | 规则引擎检视时间轴，提出**受限的样式补丁** |

实测 trace（`reports/acceptance-evidence.json → A8_agent.rule_based_traces`）：

```json
{
  "kind": "proposal",
  "mode": "RULE_BASED",
  "roles": ["DIRECTOR", "REVIEW"],
  "reason_codes": ["SCENE_PLAN_REQUESTED", "HUMAN_REVIEW_REQUIRED"],
  "patches": [{"path": "/bible/style", "value": "克制的数字博物馆编辑风格"}],
  "findings": [],
  "tool_calls": ["inspect_timeline", "get_scene_bible", "validate_citations"],
  "input_hash": "713749da9fab39965c4e90b0e97eb87a294447b0e1a9ad2d29fede2cdad34895",
  "policy_version": "controller-1",
  "review_state": "PENDING",
  "tool_results": [
    {"tool": "inspect_timeline", "output_hash": "c6c3f62dbb1469dfa068853d5d53108365d5d42717dbc1b78d30d080b041ed1d"},
    {"tool": "get_scene_bible", "output_hash": "31bca6af45a6d50b6aa684fa802e52612676a86956149a8c552dce3efc390441"},
    {"tool": "check_scene_constraints", "output": []},
    {"tool": "validate_citations", "result": "VALID"}
  ],
  "base_version": 2,
  "max_turns": 2
}
```

边界：
- **不能授予批准**（`review_state` 停在 `PENDING`，等待人工）。
- **不能改写历史事实**。工具 `validate_citations` 会返回 `VALID`/非 `VALID`，史料断言的修改必须走人工审核链路。
- 补丁范围受限（当前为 `/bible/style` 这类样式字段），不触碰事实字段。
- 相同输入哈希 → 相同提案，便于复现与回归。

### 2.3 `LIVE_LLM` — 保留骨架，**未开通**

| 维度 | 事实 |
| --- | --- |
| truth_level | **`blocked`** |
| available | **false** |
| deterministic | false |
| produces_proposal | **false** |
| requires_approval | true |
| 是否发起网络请求 | **否** |
| API key | **未配置**（`openai_key_configured: false`） |

对外 notes 原文：

```
BLOCKED: LIVE NOT VERIFIED
No API key is configured in this environment.
No request is sent to any external service.
Requests are refused with HTTP 409 so no record can imply a live model answered.
```

**设计意图（关键）**：即使有人误调用该模式，也不会产生任何外部请求，更不会留下"由大模型生成"的审计记录。`LIVE_LLM` 不在 `RUNTIME_MODES` 里，调用直接返回 HTTP **409**，响应体带 `BLOCKED: LIVE NOT VERIFIED`。

> 只有在真实接入外部模型、验证过链路、并由项目所有者书面授权后，才允许把 `available` 改为 `true`。本轮**没有**这个条件。

### 2.4 `MOCK_TEST` — 仅测试

| 维度 | 事实 |
| --- | --- |
| truth_level | `test_only` |
| available | false（对真实调用不可用） |
| deterministic | true |
| produces_proposal | false |
| 用途 | 仅供 `tests/test_agent_providers.py` 等自动化测试作为确定性夹具使用 |
| notes | `Test-only. Refused outside the automated test harness.` |

---

## 3. 可用性对照表

| 模式 | 运行时可选 | 可产生提案 | 需人工批准 | 访问外部服务 | 用凭据 |
| --- | --- | --- | --- | --- | --- |
| `MANUAL` | ✅ | ✅（记录型） | ✅ | ❌ | ❌ |
| `RULE_BASED` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `LIVE_LLM` | ❌ | ❌ | — | ❌ | ❌ |
| `MOCK_TEST` | ❌ | ❌ | — | ❌ | ❌ |

---

## 4. 系统如何强制这条边界

1. **注册表即事实源**：`app/v2/agent_providers.py` 中 `PROVIDERS` 字典是唯一真值来源，`describe()` / `catalogue()` 直接由它派生，`/api/v2/agent-providers` 与 `/api/v2/capabilities` 输出同一份数据，不存在第二份手写文案。
2. **运行时白名单**：`RUNTIME_MODES = ("MANUAL", "RULE_BASED")`。模式不在白名单 → 直接 409。
3. **拒绝即证据**：被拒绝的调用返回带 `BLOCKED: LIVE NOT VERIFIED` 的 409，而不是 404 或假成功，避免调用方误以为"重试即可"。
4. **提案自带来源标记**：每条提案记录 `mode`、`input_hash`、`policy_version`、`tool_calls`、`tool_results`，可从审计链反查提案到底由谁产生。
5. **不自动批准**：所有模式的 `requires_approval` 均为 `true`；`RULE_BASED` 产出的提案 `review_state` 恒为 `PENDING`，必须由人推进到 `APPROVED`。
6. **不静默改事实**：涉及史料断言的修改必须通过 `validate_citations` 与人工审核；Agent 无法自行修正历史事实。

---

## 5. 能力矩阵（对外声明）

| 能力 | MANUAL | RULE_BASED | LIVE_LLM |
| --- | --- | --- | --- |
| 生成受约束的样式提案 | 记录型 | ✅ | — |
| 检视时间轴 | ✅（人工看） | ✅（工具） | — |
| 校验引用 | ✅（人工看） | ✅（工具） | — |
| 自动批准 | ❌ | ❌ | — |
| 改写历史断言 | ❌ | ❌ | — |
| 触发外部网络 | ❌ | ❌ | ❌（未开通） |
| 需要人工复核 | ✅ | ✅ | — |

---

## 6. 相关文件与复现

| 文件 | 作用 |
| --- | --- |
| `app/v2/agent_providers.py` | 模式注册表、真值描述、`BLOCKED_REASON` |
| `app/v2/api.py` | `/capabilities` 暴露 `agent_modes` 与 provider 目录；agent 运行守卫 |
| `app/v2/compat.py` | 原站视频工厂适配器；provider-status / provider-models 对外暴露同一真值 |
| `tests/test_agent_providers.py` | 7 个用例，覆盖可用性、拒绝路径与目录结构 |

复现：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_agent_providers.py -q
.\.venv\Scripts\python.exe scripts\collect_acceptance_evidence.py
# 目录：GET http://127.0.0.1:8002/api/v2/agent-providers
# 拒绝：POST 运行参数 mode=LIVE_LLM → 409 BLOCKED: LIVE NOT VERIFIED
```

---

## 7. 后续轮次若要开通 `LIVE_LLM`

需要**同时**满足（缺一不可）：

1. 用户提供合规的外部模型凭据与明确的费用预算上限；
2. 实现真正的 provider 适配器（含超时、重试、错误映射）；
3. 在 `AgentProvider` 中把 `available` 改为 `true`、`produces_proposal` 改为 `true`，并更新 notes（移除 `BLOCKED` 字样）；
4. 补齐对应测试（成功路径、失败路径、超时路径）；
5. 在 `FINAL_ACCEPTANCE_A0_A12.md` 的 A8 行更新真实证据。

在满足之前，系统保持现状：**宁可显式拒绝，也不产生虚假的模型记录。**
