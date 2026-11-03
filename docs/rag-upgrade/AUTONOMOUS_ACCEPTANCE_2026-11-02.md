# 百骑谱自动知识库与可信引文 RAG：实际交付验收

日期：2026-11-02。分支：`feat/rag-core-major-upgrade`。本报告替代“等待人工 APPROVED 后才可问答”的产品阻塞策略；不声称专家审核、历史事实金标准或付费模型验收。

实现提交：`f2d8c14`（自动来源与机器引文）、`18ca960`（原站界面与真实视频验收）、`3ff2a5c`（Wikidata 候选隔离与固定快照重放）。验收资料在后续独立提交中保存，便于按阶段回滚。

## 可直接演示

本地原站演示地址：**http://127.0.0.1:5176/**；AI 客服：**http://127.0.0.1:5176/chat**。API 在 `127.0.0.1:8004`。这些是仅本机监听的开发实例，使用 `runtime/autonomous-demo-path.txt` 指向的隔离数据库，不是公开部署。

原站原有 5173/8002 实例保留。黑金首页、导航、字体、背景和原编译资源保留；没有启用浅色 React 草稿。新增界面限于原文证据区，以及修复视频工作台手机横向溢出的独立 CSS。

可以依次输入：

1. `赤兔的史籍出处是什么？`
2. `乌骓的原文`，再追问 `它的史书原文呢？`
3. `的卢的史料有哪些？`
4. `赤兔在三国演义里如何描写？`
5. `赤兔和的卢的来源比较`
6. `苍麟驹的史料出处`：明确证据不足。
7. `我重视责任和守护，哪匹马适合我？`：文化趣味匹配，不称心理测评、不附商品。
8. `推荐赤兔周边商品，预算600元`：查询真实库存与价格；预算不足时不推荐超预算商品。

前三项已经在原聊天输入框实际提交，并从返回的引文链接打开对应精确原文页。页面显示 MACHINE_VERIFIED、未人工审核、来源版本与 CC BY-SA 许可。

## 完成内容

| 范围 | 实际实现与验收 |
|---|---|
| 自动获取 | 官方 MediaWiki 搜索、限定古代作品、固定修订获取、上游 SHA-1 与渲染哈希、保留原始快照、段落提取、繁简检索、限额、缓存、失败隔离、dry-run、幂等增量导入、固定版本清单重放 |
| 证据使用策略 | 保留原 APPROVED 路径；增加 AUTO_VERIFIED_SOURCE，独立记录获取、来源、许可、机器核对、文献类型与人工审核状态。机器引文不自动成为已证实事实 |
| 实体与关系 | 100 个 Horse、11 个 Work、10 个作者／编者 Person；段落 MENTIONS 候选、作品版本关系、书目作者归属。歧义身份与事件语义未自动宣称已证实 |
| 统一 RAG | 图鉴、原 V1 聊天、V2 检索／问答、Research Agent、视频项目使用同一证据仓库；历史／文学筛选、别名、指代追问、多实体比较、精确引用、许可／隐私／版本变化失效 |
| 客服 | 恢复名马匹配、文化互动与有购买意图时的商品推荐，独立于史料证据；检查库存与预算 |
| Agent | 实际执行实体检索、证据检索、来源比较、证据关系与覆盖检查；可受限发现和入库原文；没有 approve-claim、shell、任意网址或付费模型工具 |
| 视频 | 复用已有 CPU FFmpeg 与 DAG。机器引文需要 SOURCE_ATTRIBUTED／LITERARY_ATTRIBUTED 标签及原文子串校验；实际视频显示来源、版本、许可及未人工审核提示 |
| 原站兼容 | 原聊天、图鉴、登录、抽卡收藏、商品与沙盒订单流程通过；原工作台浏览器完整出片、播放和下载通过 |

## 真实数据覆盖

以 `reports/rag-upgrade/autonomous/corpus_coverage.json` 为准：

- 自动取得 **22 个许可明确的文献页面版本**；其中 **17 个版本**提供当前可用引用。
- **81 条机器核对通过的引文关系，覆盖 32/100 匹图鉴名马**。同一段落可对应多个实体，因此 81 不等于 81 个独立史料见证。
- 其余 68 条：35 条本轮定向搜索未找到候选，31 条候选不满足作品／许可策略，2 条未获得可精确匹配的段落。未找到不等于历史上不存在；部分图鉴名称可能属于创作、别称或同名词，未伪造补齐。
- 人工审核数 **0**，机器没有把 DRAFT 改成专家 APPROVED。早期宽松名称匹配产生的候选保留版本历史，但不再进入有效引文；例如普通“虎步”用语不计作该名马的证据。
- 源文档、实体和已有业务数据没有不可逆删除。原始来源响应与数据库留在忽略的 runtime 目录，Git 提交代码、出处清单和验收记录。

旗舰来源包括《三國志/卷07》修订 2452141、《史記/卷007》修订 5978360、《三國志/卷32》修订 2583378，以及《三國演義》对应篇章。每条实际回答包含原文、段落位置、本地版本、源站固定版本链接、署名与许可；并明示这只是文献如何记载。

## 实测结果与边界

- 后端：**88 项通过**，最终机器报告为 `reports/rag-upgrade/autonomous/full-tests.xml`；覆盖原系统回归、错引文／错偏移／错版本／错马、许可不明与收紧、私密资料、失效、提示注入、重复入库、图谱、Agent 失败替代、Wikidata 隔离和固定版本重放。
- 前端：3 项 Node 测试通过，TypeScript 检查通过，原站打包成功。
- 业务 HTTP：**16 项通过**；支付仅为原有 sandbox，没有实际支付或发货。
- 浏览器：桌面与手机 **16 个页面检查通过**，无脚本异常和页面横向溢出；三匹名马原聊天→精确原文流程通过；文化匹配和真实研究工具展示通过。
- 原视频工厂：状态“完成 100%”，预览返回 `200 video/mp4`，下载按钮可用。
- 单独的史料引文视频：CPU DAG 状态 SUCCEEDED，使用真实《三国志》引文，无外部生成调用。
- 保护检查：原运行库 SHA-256 未变，原站 32 个编译资源哈希未变，接手时已有的 `reports/original-video-factory-v2.json` 未提交修改的内容哈希未变。
- 重放：离线固定版本清单 dry-run 已实际执行；完整重复入库的前后知识快照相同，网络请求为 0。

完整样例与实验在 `rag-comparison.json`。同一来源快照上，32 个自动构造的实体出处查询，Top-5 找到同一自动关联实体的引文：字符余弦 **29/32**，BM25 **31/32**，统一实体约束检索 **32/32**。这是**机器关联代理检查，不是独立人工金标准**，不能解释为历史准确率、专家引用准确率或通用召回率。旧 APPROVED 全局门槛可用引文 0，新机器引文轨道可用 81。

本机九个样例请求中位耗时约 **645 ms**，最大约 **791 ms**；非生产压测。固定／单轮／自适应 Agent 都实际运行了工具，但本组样例中自适应并未始终减少调用；没有宣称算法普遍优于基线。

`agent-acquisition-trace.json` 记录真实 8 次工具调用：检索无有效证据→发现目标章节→读取缓存的真实 API 版本→机器核对并入库→重新检索。隔离验证库从 0 条机器引文变为 1 条。此次验收明确标记 CACHE；实时网络获取及 FETCHED 哈希另见采集批次记录，没有把缓存冒充新网络请求。

## 启动、重现和回滚

在项目根目录的 PowerShell 中：

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
$db = (Get-Content runtime/autonomous-demo-path.txt).Trim()
.venv/Scripts/python.exe scripts/run_v2.py api --database $db --port 8004
```

另外两个终端启动同一数据库的 CPU worker 和原站：

```powershell
$db = (Get-Content runtime/autonomous-demo-path.txt).Trim()
.venv/Scripts/python.exe scripts/run_v2.py worker --database $db
cd frontend
npm install
npm run dev -- --mode rag-auto
```

从项目已有基线建立新的隔离副本并获取材料：

```powershell
# 新副本，不覆盖原库；可通过 --copy-from 指定已有项目内 SQLite 基线
.venv/Scripts/python.exe scripts/autonomous_sources.py --new-copy --apply --seed-only
# 对 100 个真实目录项进行有上限的发现
.venv/Scripts/python.exe scripts/autonomous_sources.py --apply --entities all --max-requests 220 --max-pages 45
# 当前快照离线 dry-run；不会提交数据库修改
.venv/Scripts/python.exe scripts/autonomous_sources.py --manifest reports/rag-upgrade/autonomous/source-manifest.json --offline --max-pages 30 --max-requests 80
# 按固定修订重新获取（联网）；默认仍 dry-run，需要写副本时加 --apply
.venv/Scripts/python.exe scripts/autonomous_sources.py --manifest reports/rag-upgrade/autonomous/source-manifest.json --max-pages 30 --max-requests 80
.venv/Scripts/python.exe scripts/wikidata_discover.py --apply
```

新 clone 不包含用户业务数据库和采集缓存，应先按现有启动文档建立基线库，或使用自己拥有的项目内数据库副本。离线重放依赖本轮 runtime 缓存；没有缓存时会明确报 CACHE_MISS。在线固定修订重放仍校验渲染哈希，模板或上游状态改变时不会冒充原快照。

复验命令：

```powershell
.venv/Scripts/python.exe -m pytest tests -q --basetemp runtime/acceptance-new
.venv/Scripts/python.exe scripts/autonomous_browser.py
.venv/Scripts/python.exe scripts/autonomous_acceptance.py
.venv/Scripts/python.exe scripts/autonomous_video.py
.venv/Scripts/python.exe scripts/rag_business_smoke.py --api http://127.0.0.1:8004 --report reports/rag-upgrade/autonomous/business-smoke.json
```

回滚无需删除数据：停止这组 5176/8004 进程，继续使用原 5173/8002 实例；数据库切回此前副本，Git 以增量 revert 选择对应功能提交。原库与原资源没有迁移覆盖，历史 Revision 保留。

## 尚未完成／外部阻塞

- **BLOCKED_UPSTREAM_MAXLAG**：Wikidata 正式候选导入遵守源站 maxlag 拒绝；搜索可访问不能视为已导入。后续可正常重试，不能取消限制来冲过源站保护。
- **QUARANTINED**：HF/Kaggle 部分候选许可血缘与具体版次未解决；GitHub API 限流；CText 未具备授权条件。替代主链路已使用维基文库，不阻塞产品。
- 68 匹马尚无有效原文；人物／事件／年代多跳的语义核验、自动语义矛盾判断和自动事实综合仍不完整。目前自动候选以 MENTIONS 展示原文，不把相似文字等同已证实身份、归属或事件。
- 无人工金标准；历史准确率、专家引用准确率、标注者一致性均 **UNVERIFIED**。
- Dense／混合检索、学习型路由、LLM 与 Jev 实际付费调用及公开部署 **未执行**。未证明相对当前基线的收益，也没有消费 AI 订阅之外的 API 额度。
- 未配置后台周期采集服务；提供可重复运行的受限 CLI 与站内 Agent 工具。来源状态超过七天会停止作为有效机器引文，需重新获取核对。

源站／许可详情见 [SOURCE_PROVIDER_INVENTORY.md](SOURCE_PROVIDER_INVENTORY.md)。原站截图在 `reports/screenshots/autonomous/`；浏览器录像在 `runtime/auto-browser-demo.webm`；两段真实视频分别为 `deliverables/autonomous-source-quote.mp4` 与 `deliverables/autonomous-original-factory.mp4`。这些本机媒体不推送到 GitHub。
