# 百骑谱发布候选：本地启动与五分钟演示

推荐唯一入口：`scripts/resume_demo.py`，原黑金站 `http://127.0.0.1:5178`，API `http://127.0.0.1:8006`。API 与 CPU Worker 共用 `runtime/resume-rc/autonomous-demo.db`。只监听本机，不是公开部署。

## 新环境准备（Windows / Python 3.13）

在项目根目录使用 PowerShell。Windows/Python 3.13 的完整解析依赖固定在 `requirements-resume-windows-py313.lock`，其他平台以 `requirements-dev.txt` 为起点另行验证。需要 Node、FFmpeg/FFprobe、已授权中文字体；浏览器验收使用本机 Edge。运行数据和密钥均写入忽略的 runtime；不复制旧账户、订单、私有媒体或原运行数据库。

```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-resume-windows-py313.lock
npm.cmd --prefix frontend ci
.venv/Scripts/python.exe scripts/resume_demo.py init
.venv/Scripts/python.exe scripts/resume_demo.py replay --manifest docs/resume-readiness/flagship-manifest.json --max-pages 4
.venv/Scripts/python.exe scripts/resume_demo_preflight.py --database runtime/resume-rc/autonomous-demo.db --manifest docs/resume-readiness/flagship-manifest.json --offline
.venv/Scripts/python.exe scripts/resume_demo.py start
```

`init` 拒绝覆盖已有数据库。首次联网从官方 API 重放四个固定版本，检查哈希与许可；不能访问时报告具体阻塞项，不生成假资料。初始化将仓库的编辑图鉴写入空库，以恢复原有文化匹配；这些编辑内容仍不是历史证据。唯一新增商品明确标为“演示商品·赤兔书签（沙箱无实物）”，价格、库存只用于本地业务测试。

全新 clone 没有原文缓存，直接 `replay --offline` 会失败，这是预期行为。已经联网取得缓存后才可离线回放。仓库只保存出处清单、许可和哈希，不打包整库或权利未明图片；本地旧站图像的存在不等于取得公开再分发许可。

需要扩展到本次 22 个许可版本时：

```powershell
.venv/Scripts/python.exe scripts/resume_demo.py replay --max-pages 22
.venv/Scripts/python.exe scripts/resume_demo.py replay --offline --max-pages 22
```

## 每次演示前

运行上面的 preflight。它只读检查数据库、版本、缓存、许可、当前可引用数量、观察时间、工具、字体和端口；报告默认在 `reports/resume-readiness/preflight.json`。ATTENTION 不等于整个站点无法运行，应查看具体缺失或失效来源。

需要联网刷新时显式执行有限批次：

```powershell
.venv/Scripts/python.exe scripts/resume_demo_preflight.py --database runtime/resume-rc/autonomous-demo.db --manifest docs/resume-readiness/flagship-manifest.json --refresh-pages 4
```

刷新上限六页，保留 FETCHED/CACHE/FAILED 区别，遵守 maxlag 与限速。当前引文要求最近七天成功观察；过期或临时网络错误时，可从证据区的“保存快照 · 非实时”链接浏览经完整性校验的原文，不能当作刚刚联网验证。许可收紧、不可用、私有化、撤回或哈希错误不会通过离线模式放行。重放缓存不能抹掉更近的失败观察。

## 五分钟演示顺序

1. 首页、图鉴、抽卡和商城：确认原黑金站保留。注册本地演示账户；不使用旧用户凭据。
2. AI 客服依次输入“赤兔的史籍出处是什么？”、“乌骓的原文”、“的卢的史料有哪些？”。阅读简短摘要，展开完整原文，点击段落链接查看作品、固定版本、位置、署名和 CC BY-SA 许可。
3. 输入“赤兔出生于哪年哪月哪日？”观察明确拒答；输入“的卢在三国演义里的故事原文”观察文学归属。机器核对证明引用匹配，不能自动证明史实。
4. 在局部证据面板点击“研究与来源比较”，查看真实工具 trace。规则规划标为 RULE_BASED，模型调用和费用为零。缺失资料获取每用户每小时最多三次、全实例十二次，同时只运行一轮；每轮还有页面、请求、时间和调用预算。
5. 视频工厂创建短片，运行 CPU DAG，等待完成后播放/下载。样片 `deliverables/resume-source-quote.mp4` 是 FFmpeg 程序化合成，不是视频大模型生成。演示录像在 `runtime/resume-rc/browser.webm`。

独立的真实资料失败场景复验：`scripts/resume_failure_demo.py`。脚本创建新的隔离副本，验证重复导入不增数、来源撤回后引用过期，不撤回正式演示库材料。

## 停止、重启与排错

```powershell
.venv/Scripts/python.exe scripts/resume_demo.py stop
.venv/Scripts/python.exe scripts/resume_demo.py start
```

停止只处理启动器记录的 PID 且核对进程创建时间；记录保留。端口占用时启动器报错，不杀其他程序。日志与 PID 在 `runtime/resume-rc/`；重启保留账号、资料和任务。不要同时从两个目录启动同一组端口。

历史入口 5173/8002、5175/8003、5176/8004 分别属于原开发、旧 RAG QA、自动来源 QA，不能混用它们的登录态、数据库和 Worker。保留历史实例不代表应继续按它们投递演示。

付费 LLM、Jev、外部视频生成及公开发布默认关闭。本轮没有获得这些调用或部署授权。
