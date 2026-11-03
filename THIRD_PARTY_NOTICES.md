# 第三方软件与素材记录

前端包为 npm 原包依赖，版本锁定于 frontend/package-lock.json；未修改第三方源码。源码/包许可副本见 docs/licenses，完整 npm 依赖许可证元数据见 docs/frontend-sbom.json。下表不是对现代图片、模型或服务的授权。

|组件|本地验证版本|许可证元数据|
|---|---|---|
|react|19.3.1|MIT|
|react-dom|19.3.1|MIT|
|vite|8.3.5|MIT|
|typescript|5.9.3|Apache-2.0|
|@xyflow/react|12.12.0|MIT|
|@tiptap/core|3.32.2|MIT|
|@tiptap/react|3.32.2|MIT|
|@tiptap/starter-kit|3.32.2|MIT|
|@tiptap/pm|3.32.2|MIT|
|@xzdarcy/react-timeline-editor|1.0.0|MIT|
|fastapi|0.115.12|see package classifiers|
|sqlalchemy|2.0.41|MIT|
|alembic|1.15.2|MIT|
|pydantic|2.11.3|MIT|
|uvicorn|0.34.3|BSD-3-Clause|
|Pillow|12.0.0|MIT-CMU|
|pytest|8.4.2|MIT|
|ruff|0.17.3|MIT|
|playwright|1.64.1|Apache-2.0|
|huey|3.5.3|see package classifiers|

- React Flow：DAG 投影；后端执行不依赖画布。Tiptap：仅使用开源核心；未启用付费云协作。React Timeline Editor：连续场景的三轨视图；不是另一个渲染器。
- FFmpeg/FFprobe：使用本机已有 CLI，未把二进制打包进仓库。本机构建参数见 reports/ffmpeg-build.txt，含 --enable-gpl 和 libx264；分发二进制时须单独满足对应许可证。官方说明：https://ffmpeg.org/legal.html 。
- 字体：本机 Windows 微软雅黑只用于本地渲染，复制到 ignored runtime；不随源码/交付包再分发。跨平台请自行提供已授权的中文字体并设置 STEEDATLAS_FONT。源代码不附微软字体。
- 演示三张图：media.template() 原创几何插画；音轨：FFmpeg 合成测试音，不是配音/克隆声音。可复现素材生成脚本已提供。
- 旧站名马图片：保留既有资源，使用权待用户核验；没有公开发布。旧代码与研究附件的权利归原权利人，不因本次归档重新授予开源许可。
- 古典短引文：保留来源 URL/章节定位，digitization/edition 权利另列待审；三例默认 DRAFT。不得据此宣称整库内容已清权。
- Huey 仅做隔离 POC，不是核心运行依赖。Pydantic AI/LangGraph/Rendiv/OTIO/PySceneDetect/整套视频平台均未纳入核心；没有声称它们已通过本地集成验收。
- 全量依赖的 UNDECLARED/非标准 license 元数据需要发布前进一步人工核验；目前不宣称通过完整法律审计。
