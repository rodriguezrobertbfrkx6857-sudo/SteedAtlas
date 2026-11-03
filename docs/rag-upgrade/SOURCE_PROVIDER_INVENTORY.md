# 自动史料来源清单（2026-11-02 实测）

本轮采用定向查询、官方 API、固定版本和有限批次。源站失败或许可不明只隔离对应候选；不要求人工 APPROVED 才能展示经过机器核对的原文。许可判断与史实判断分开。

| 来源 | 实际结果 | 版本／许可 | 产品用途与限制 |
|---|---|---|---|
| 中文维基文库 MediaWiki API | 已真实采集、清洗、入库和引用 | 每页 `revid`、上游 SHA-1、原始 HTML 哈希、提取文本哈希；siteinfo 实测 CC BY-SA 4.0 | 主链路；仅允许清单内古代原作，排除现代翻译；原文及版本归属核对，不证明事件真实 |
| Wikidata | 首次连接失败；后续搜索 HTTP 200；正式带 `maxlag=5` 的批次被源站 `maxlag` 拒绝 | CC0；赤兔搜索实际返回 Q1321898、Q123597208、Q11351976 三个不同候选 | 已实现限额、版本化候选适配器和查询 API。当前正式导入批次 BLOCKED_UPSTREAM_MAXLAG，未绕过限制。候选不自动合并、不成为历史引文 |
| Hugging Face `gujilab/chinese-classical-corpus` | API 元数据及固定提交 README 均 HTTP 200；未下载正文大文件 | 提交 `1979f15b4b749b3601fd9ee3e4111a725c079439`；卡片称 CC0 | README 同时列出殆知阁、ctext、chtxt、chinese-poetry、NiuTrans 等上游，尚未逐段解决许可和版本归属。QUARANTINED；未将译文或指令数据当史料 |
| Kaggle `qianboao/chinesepoetrydataset` | 官方元数据 API HTTP 200 | version 2；声明 CDLA-Permissive-1.0 | 卡片提供规模与格式，但缺具体数字底本、作品位置和上游链条，QUARANTINED；仅保留元数据 |
| Kaggle `jerry0723/chinese-poems-with-chinese-annotations` | 页面没有可读取的许可／正文内容 | 未验证 | 未复制现代注释；转向许可更清楚的维基文库 |
| GitHub `chinese-poetry/chinese-poetry` | 官方 LICENSE 页面可读；公共 API HTTP 403 RATE_LIMIT | 仓库 LICENSE 为 MIT；未取得此次固定数据提交 | 不将仓库软件许可自动等同每一条数字文献的版次证明；没有绕过限流下载 |
| Project Gutenberg | 已读取机器人访问政策 | 按具体书籍、所在地公版条件处理 | 本轮未批量获取；对旗舰三匹马的原始中文版本，维基文库更直接 |
| Chinese Text Project | FAQ 网页访问返回 403；未调用内容接口 | API 权限／用量条件未具备 | BLOCKED；没有爬虫、验证码绕过、IP 轮换或经 HF 间接洗掉上游限制 |

依据与入口：

- [MediaWiki 原文 API](https://www.mediawiki.org/wiki/API:Get_the_contents_of_a_page)、[修订接口](https://www.mediawiki.org/wiki/API:Revisions)、[API 访问政策](https://www.mediawiki.org/wiki/API:REST_API/Policies)。
- [维基文库再利用说明](https://en.wikisource.org/wiki/Wikisource:Reusing_Wikisource_content)、[本轮实际站点许可接口](https://zh.wikisource.org/w/api.php?action=query&meta=siteinfo&siprop=rightsinfo&format=json)、[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。
- [Wikidata 许可](https://www.wikidata.org/wiki/Wikidata:Licensing)、[Wikidata 数据再利用](https://www.wikidata.org/wiki/Wikidata:Reuse)。
- [HF 数据卡](https://huggingface.co/datasets/gujilab/chinese-classical-corpus)、[Kaggle 元数据](https://www.kaggle.com/api/v1/datasets/view/qianboao/chinesepoetrydataset)、[GitHub LICENSE](https://github.com/chinese-poetry/chinese-poetry/blob/master/LICENSE)。
- [Gutenberg 机器人政策](https://www.gutenberg.org/policy/robot_access.html)、[许可说明](https://www.gutenberg.org/policy/permission.html)、[CText FAQ](https://ctext.org/faq)、[CText API](https://ctext.org/tools/api/ens)。

工程细节：

- 官方接口固定域名；UA 附项目地址；串行至少一秒间隔，默认最多 30 次请求，命令行硬上限 300 次／100 页。Agent 每次最多 9 次上游请求、2 页、10 次工具调用，45 秒开始调用的总预算，单个在途请求另受超时约束。
- 没有无限重试。429、403、maxlag、网络失败均记录；搜索失败时尝试预先声明的目标章节，仍失败则继续本地已有证据。
- 仅古代作品允许清单可入库；这是获取与呈现政策，不是作品可靠性评分或现代校勘本认证。标题相似、现代译注、许可链不清的候选不会自动获准。
- 原始 wikitext 与渲染 HTML 保存在隔离数据库的私有 source_document；同修订号下模板渲染仍可能变化，因此同时固定渲染哈希。段落偏移属于确定性提取文本；正文未做繁简改写，繁简转换仅用于检索。
- 每次引文使用重新检查版本、完整段落、偏移、哈希、许可、公开性和实体候选。在线重新获取失败会使依赖失效；成功观察的有效期为 7 天。离线重放不会延长观察时间。未配置自动后台定时刷新，运行刷新命令即可更新。
- 原文引用保留作品名、维基文库贡献者、固定版本链接、CC BY-SA 链接和提取说明。报告中的维基文库摘录按同一 CC BY-SA 4.0 条款提供；古代作品的公版地位与现代转录署名义务分别记录。
- 来源独立性以作品合并作为保守线索；自动关系为 MENTIONS，不将抄录、诗文典故或重复页面计作独立事实支持。

实测原始记录见 `reports/rag-upgrade/autonomous/provider-probes.json`、`wikidata-candidates.json`、`source-manifest.json` 和采集批次报告。没有实际取得的数据正文不计入覆盖率。
