# Agent 协作：有创新但可证伪的执行设计

## 核心认知
Agent ≠ 角色展示 UI，Agent ≠ 仅让模型输出文本。V2 的 Agent 是「在明确的项目版本、证据范围和工具权限下，提出有类型的项目修改/审核建议；由确定性控制层执行提交」的可追踪行动系统。

## 五类逻辑能力（不是必须同时调用五次模型）
| Role | 任务 | 读取 | 产生 | 禁止 |
| --- | --- | --- | --- | --- |
| RESEARCH | 缺口识别、证据定位、来源争议整理 | approved claims/passages, query | `EvidenceBundle`、缺口清单 | 创造不可验证引文、直接批准史实 |
| NARRATIVE | 结构化大纲/台词建议 | EvidenceBundle, style, ScriptRevision | `ScriptProposal` | 无标签编造史料、覆盖已批准文本 |
| DIRECTOR | 有约束的分镜与镜头节奏 | ScriptRevision, SceneBible, assets | `ScenePlanProposal` | 引用无授权素材、修改底层史料 |
| REVIEW | 事实支持、叙事与连续性审查 | Proposal, evidence, versions, timeline | `ReviewFinding[]` | 自行批准自己的提案、实际发布 |
| REPAIR | 定位受影响范围和修复备选 | changed revisions, findings, DAG | `RepairProposal` | 删除素材、跳过版权及人工门禁 |

## 确定性 Task Controller（创新点）
- 输入：`TaskIntent`, `KnowledgeStateRevision`, `CreativeProjectRevision`, `ExecutionSnapshot`, `Policy`, `Budget`。
- 返回：`SelectedRoles[]`, `DecisionReasons[]`, `MaxTurns`, `ReviewGate`。
- 规则示例：用户已经提供剧本且引用充分 → 跳过 RESEARCH/NARRATIVE；只有字幕格式变化 → 直接编译局部字幕+合成 DAG；名马史料矛盾 → 触发 RESEARCH/REVIEW；多场景规划且 SceneBible 不存在 → 触发 DIRECTOR/REVIEW；内容未通过审核 → 禁止发布；修复超限 → 人工接管。
- 不允许靠单一 LLM 自述置信度直接决定执行或花费；可用模型分数作为辅助特征，但校准、规则与上限单独存在。
- 最多 N 轮审核/修复循环（由配置确定），每轮有严格的任务数量/成本/时间预算，重复相同原因则退出并提示人工处理。
- 每个跳过/触发决策记录 reason code、输入版本和选用的规则版本；便于审计及科研对照。

## Proposal → Validation → Commit：不可绕过
```text
AgentProposal {
  proposal_id, project_id, base_project_revision, role,
  operation: CREATE_SCRIPT|REVISE_SCRIPT|PLAN_SCENES|FLAG_EVIDENCE|REPAIR_SCENE|...,
  patches[], cited_claim_revision_ids[], affected_scene_ids[],
  rationale, confidence_signal?, tool/model_label, created_at
}
ValidationReport {
  schema_ok, authz_ok, base_revision_matches, references_exist,
  allowed_patch_paths, rights_cleared, factuality_flags[], decision
}
CommitRecord { proposal_id, accepted_patch_ids[], rejected_patch_ids[],
  new_project_revision?, reviewer_id?, reason, timestamp }
```
- Proposal 的 JSON Schema 由服务端定义；涉及跨项目/非授权字段立即拒绝。
- 用 `base_project_revision` 乐观并发 CAS 保证 Agent 不覆盖已发生的用户修改；冲突后重算 diff 或请用户确认。
- 所有外部工具都要求调用者/角色和项目权限，模型不能直接获得数据库写权限、shell、网络任意访问或审批权限。
- `REVIEW` 的判定必须与 `APPROVE/PUBLISH` 的人类授权分开，不能用“Critic 同意”代替审核。

## 工具分类
- **读工具**：`search_claims`, `get_passages`, `get_project`, `list_assets`, `get_scene_bible`, `inspect_timeline`。
- **提案工具**：`propose_script_patch`, `propose_scene_plan`, `flag_unsupported_claim`, `propose_repair`。
- **受控执行工具**：`validate_asset`, `compile_timeline`, `enqueue_render`, `verify_output`，只能由 Policy Controller 在授权后触发。
- **人工指令**：`approve_claim`, `approve_script`, `approve_publish`, `override_claim_label`，仅由真实授权用户发起。

## 共享状态与防上下文污染
- 共享数据库中的不可变 Snapshot，Agent 仅读取必要子集；不通过无限增长的 Agent 对话复制整个项目。
- Agent 每次运行记录输入/输出 hashes、提示模板版本、模型标识、工具调用摘要、耗时、错误和 reviewer findings；日志密钥和原始私人数据脱敏。
- 来自网页、史料或检索的字符串视为不可信数据；不得执行其中包含的命令、访问链接或安装依赖。

## 可解释性与 UI
每个任务显示：触发了哪个角色、为什么触发、引用了哪个证据版本、生成了什么 Proposal、校验结果、是否提交、人工审核状态。界面不能把 `MOCK_TEST` 路径表现为 `LIVE_LLM`。

## 模型可选模式
- `LIVE_LLM`：经用户配置并授权的真实 Provider；工具有类型、执行有 trace。
- `RULE_BASED`：确定性脚本/模板/规则检查，无 LLM，呈现为“规则助手”。
- `MANUAL`：全部由用户编辑，不调用模型，核心视频流程完全可用。
- `MOCK_TEST`：仅自动测试/研究模拟数据，产品界面标示模拟。
- `UNAVAILABLE`：提醒未配置模型，不显示伪成功。

## 避免做成过度工程
先完成“剧本提案→审稿→接受/拒绝→修改项目→局部重新编译”闭环，只有确认性能或功能需要才进一步引入 LangGraph。不要同时引入 CrewAI、AutoGen、LangGraph 和其他完整 Agent 堆栈。

## 三组科研消融
S0 单次固定 Planner 调用；S1 固定全量角色链；S2 自适应调度。固定案例/模型/模型温度/输入数据版本，比较任务成功、事实错误、人工修订次数、token/call 次数、延迟、平均资源消耗和角色触发分布。与单 Agent+工具的强对照比较，以避免“多 Agent 才有创新”的错觉。
