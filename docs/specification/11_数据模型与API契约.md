# 数据库迁移、领域模型和前后端接口

## 新增/规范化模型（建议）
| 模型 | 字段重点 | 约束 |
| --- | --- | --- |
| `horse_entity` | id, slug, name, aliases, period, media | 原有 ID/URL 迁移兼容 |
| `source`/`passage_revision` | edition, rights, locator, text/hash, version | 禁止无权限任意写 |
| `claim_revision`/`claim_evidence` | status, epistemic label, support, conflict, reviewers | 不可变修订、引用必须存在 |
| `creative_project` | owner, horse_id, status, current_revision | 用户范围隔离 |
| `creative_revision` | version, previous, title, script, scope, timestamps | 乐观并发 CAS |
| `scene_bible_revision` | global/style/narrative constraints | 引用版本化 |
| `scene`/`script_segment` | ordinal, text, claim_rev_refs, duration, design | 稳定场景 ID |
| `media_asset`/`asset_revision` | SHA, type, length, owner, rights, uri | 服务端路径/下载鉴权 |
| `timeline_revision`/`timeline_track` | FPS rational, clip range, track type | 唯一有效时间基 |
| `workflow_job`/`task_node`/`attempt` | node states, edges, lease, fencing token | DB authority |
| `artifact`/`artifact_dependency` | content hash, producer attempt, lineage | verified before succeeded |
| `agent_run`/`agent_proposal`/`review_decision` | mode, inputs, patch, verdict, reviewer | Proposal 不代表批准 |
| `audit_event`/`outbox` | event type, actor, data hash, delivery status | 事件不可篡改 |

## 兼容迁移策略
- **先新增、后双读/只写新表、最后迁移旧路径**；当前 `WorkflowTask` 和 JSON 字段不在第一轮删除。
- Alembic migration 附 upgrade/downgrade 或明确不可回退的数据风险；迁移前备份并实测回滚，唯一约束和外键要检查。
- 文档清楚区分“官方源数据”、“新增推导字段”、“AI 提案”，不对 100 匹马批量编造文献或时间点。
- 旧链接和 API 若改变，应保留向后兼容层或明确 redirect/兼容版本，必要时前端做适配。

## API（建议前缀，不覆盖旧接口）
| Endpoint | 作用 | 权限 |
| --- | --- | --- |
| `GET /api/v2/horses`、`GET /api/v2/horses/{id}` | 图鉴与详情 | public |
| `GET /api/v2/search` | 搜索与证据 passage | public/rate limit |
| `GET /api/v2/sources/{id}/passages/{pid}` | 精确引用片段 | rights/visibility |
| `POST /api/v2/admin/claims` | 创建待审证据断言 | curator |
| `POST /api/v2/admin/claims/{id}/approve` | 人工批准版本 | reviewer |
| `POST /api/v2/projects` | 创建创作项目 | creator |
| `GET /api/v2/projects/{id}` | 工程快照 | owner/reviewer |
| `PATCH /api/v2/projects/{id}/revisions` | 保存有版本的 diff | owner, If-Match |
| `POST /api/v2/projects/{id}/agent-runs` | 运行授权 Agent / 规则模式 | owner/quota |
| `POST /api/v2/agent-proposals/{id}/review` | 接受/拒绝修改 | owner/reviewer |
| `POST /api/v2/projects/{id}/workflow/compile` | 预览 DAG 及影响 | owner |
| `POST /api/v2/projects/{id}/renders` | 提交 CPU 渲染 | owner/resource cap |
| `GET /api/v2/jobs/{id}`、`GET /api/v2/jobs/{id}/events` | 状态/事件 | owner |
| `POST /api/v2/jobs/{id}/cancel`、`POST /api/v2/jobs/{id}/retry` | 受控取消和重试 | owner/guard |
| `GET /api/v2/artifacts/{id}/download` | 鉴权下载 | owner/visibility |

## 输入契约规则
- 每个可写 API 验证 user_id/owner、CSRF/CORS 与认证、上传限制、预算与复杂度。
- 对编辑类 API 使用 `If-Match` 或期望版本字段；冲突返回 409 + 最新 revision summary。
- Agent 提议和编辑命令的 Schema 分开；所有 patch path 必须白名单。
- 不接受任意服务器写入路径、Shell 字符串、未验证 webhook 或内部地址。
- 返回统一 `error_code`, `message`, `request_id`, `details`（敏感字段脱敏）。
- API ID 幂等对写/重试/发布任务尤其重要；不将 GET 用于变更操作。

## 数据导出
- `ProjectExport`：版本化 JSON、所有素材清单、参考来源/版权状态、可复现时间轴、SRT、MP4（按权限）及含差异的审稿记录。
- 研究实验单独导出匿名、已清权的引用与任务记录；不包含私人上传文件、密钥和完整商业供应商响应。
