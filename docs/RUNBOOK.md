# V2 历史开发与复现

> 发布候选请优先使用 [DEMO_RUNBOOK](resume-readiness/DEMO_RUNBOOK.md)：5178/8006、空库初始化和固定来源重放。下面的端口及三条 DRAFT 策略属于历史开发说明，不能作为当前机器引文的人工审批门槛。

**界面以用户最新要求为准：默认入口为原站黑金风格，只允许微调。原站视频工厂已通过兼容层接入 V2 CPU 后端，见 LEGACY_V2_INTEGRATION.md。浅色 React 创作工作台仍为非默认草稿，其操作记录不代表原站已有同样的编辑功能。见 UI_CHANGE_POLICY.md。**

分支 `upgrade/steedatlas-v2`；旧站原目录保留。需要 Python 3.13、Node 24、已有 FFmpeg/FFprobe。没有 GPU、模型权重或付费 API 前置条件。

## 安装（项目内）

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd frontend
npm.cmd ci
cd ..
.\.venv\Scripts\python.exe scripts/run_v2.py init
```

已有本地备份时，在**尚不存在 runtime/steedatlas.db** 的条件下，可使用 `init --import-local-backup` 复制 `runtime/backups/legacy.db`；不会改写备份或原始数据库。无备份的新环境使用空库，100 份 JSON 基础图鉴仍可访问；不伪造历史账户和业务记录。

三个终端分别执行：

```powershell
.\.venv\Scripts\python.exe scripts/run_v2.py api
.\.venv\Scripts\python.exe scripts/run_v2.py worker
cd frontend
npm.cmd run dev
```

也可在端口 8002/5173 空闲时运行 `./start-v2.ps1`，以隐藏进程启动；PID 和日志在 runtime/。不要在已有实例运行时重复启动。访问 [本地网站](http://127.0.0.1:5173) 与 [API 文档](http://127.0.0.1:8002/docs)。站点仅绑定 loopback。

## 首次使用

默认原站入口：注册/登录 → 打开视频工厂 → 填写主题及分镜参数 → 创建并运行任务 → 等待 CPU 合成完成 → 预览/下载。API 与 Worker 均需运行；外部视频生成、真实 LLM 和自动发布不在当前可用链路内。

以下为非默认 React 草稿的工程编辑验证流程（`npm.cmd run dev:preview`，端口 5174）：

登录/注册 → 图鉴选马 → 创建工程 → 编辑三幕剧本 → 保存 → 上传可用素材或保留原创模板 → 选择声音/画幅 → 人工审阅 → 导出。Worker 必须独立运行。无声/上传音频都不涉及外部模型；字幕为按场景手工时间分布，非 ASR 精准对齐。

新用户默认为普通创作者。需要本地策展/审核演示时，在登录后通过 `/api/v1/auth/me` 获取该本地账户 ID，再明确执行：

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py --user-id <本地账户ID> --role admin
```

该命令只连接 runtime/steedatlas.db 并写审计；没有默认管理员密码。三个史料示例均为 DRAFT，须真人核对原始来源、关系和权利再批准。普通账户不能批准 Claim。

## 测试与样片

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --junitxml=reports/pytest.xml
.\.venv\Scripts\python.exe -m ruff check scripts tests experiments wangzhan/{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server/app/v2
cd frontend
npm.cmd test
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe scripts/browser_qa.py
.\.venv\Scripts\python.exe scripts/make_demo.py
.\.venv\Scripts\python.exe experiments/run_benchmarks.py
```

浏览器脚本使用已安装 Edge 的 headless 模式；若没有该浏览器，需要另外配置已有 Chromium，不能谎称浏览器验收通过。样片脚本通过真实 HTTP API 上传三幅原创几何图和合成音轨，调用独立 Worker 后下载 MP4/SRT。音轨为测试音，不是旁白。截图在 reports/screenshots/，视频和探测结果在 deliverables/。

## 字体、存储及跨平台

- Windows 默认使用本机已授权的微软雅黑；字体不提交。其他系统需提供中文字体并设置 `STEEDATLAS_FONT`，例如 Noto Sans CJK。FFmpeg 的 `fontfile` 采用 ASCII 相对路径，避免 Windows 中文目录导致字体回退。
- runtime/ 含私有数据库、密钥、本地字体、上传文件、任务输出和测试副本，全部被 Git 忽略。
- 生产使用必须设置 APP_ENV=production、DEBUG=false 和强 SECRET_KEY；本地启动器自行生成 ignored 开发密钥，不重用原环境凭据。
- V2_STUDIO_ENABLED 默认启用；外部媒体、旧远程动作和公开发布默认关闭。不要用开关绕过未完成的生产安全验收。

## 旧业务兼容

API 保留 `/api/v1`；旧抽卡/收藏/测试/商城构建通过本地 8002 端口的原路由 /collection、/gacha、/quiz、/product 访问（旧站与 V2 不同端口，首次需单独登录）。旧媒体缺可靠所有权元数据，默认只允许 staff 访问，须完成 ACL 迁移才能恢复普通用户访问。旧视频生成和远程发布动作冻结，迁移到 V2 CPU 工作台；不是承诺旧生成器全功能兼容。商城仍是模拟支付。

## 回退

见 ROLLBACK_PLAN.md。数据库回退验证仅在副本执行，原始历史数据库不变。新增 V2 表降级会丢失副本内的 V2 项目，应先导出；生产操作须另外授权。GitHub Actions 仅配置 workflow_dispatch，本轮没有触发云端 CI 或公开部署。
