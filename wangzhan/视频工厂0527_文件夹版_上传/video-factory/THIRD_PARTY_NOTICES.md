# 第三方参考说明

本项目的视频生成流程优化参考了以下开源项目的工作流设计思想：

- 项目：AIDC-AI/Pixelle-Video
- 地址：https://github.com/AIDC-AI/Pixelle-Video
- 许可证：Apache License 2.0

当前视频工厂没有直接复制 Pixelle-Video 的完整实现代码，而是借鉴其“线性视频流水线”和“StoryboardFrame 中间模型”的思路，并按本项目现有后端、前端、任务状态和 API 接口重新实现。

已吸收的设计点：

1. 将每个分镜视为独立的 StoryboardFrame。
2. 每个 StoryboardFrame 绑定旁白、字幕、画面提示词、镜头语言、预计时长和后续产物。
3. 关键帧、Veo 片段、合成结果都回写到同一份分镜清单里。
4. 成片输出时生成轻量质检报告，用于排查缺视频、缺片段、缺字幕、合成警告等问题。

如后续直接引入 Pixelle-Video 的源码文件，需要继续保留其 Apache-2.0 许可证声明，并在本文件中列明具体来源文件。
