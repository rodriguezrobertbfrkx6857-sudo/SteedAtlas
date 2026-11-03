# Canonical Timeline、文件资产和 CPU 出片

## Canonical Timeline 必须独立于 UI 库
```text
TimelineRevision {
  timeline_id, project_id, version, fps_num, fps_den, width, height,
  duration_ticks, tracks[], rendered_from_revision?, created_at
}
Track { track_id, kind: VIDEO|IMAGE|NARRATION|MUSIC|SUBTITLE|OVERLAY, z_index, muted }
Clip { clip_id, track_id, asset_version_id, start_tick, end_tick, source_in_tick, source_out_tick,
       effect_ids[], transition_in?, transition_out?, claim_revision_ids[], scene_id? }
SubtitleCue { cue_id, start_tick, end_tick, text, label?, claim_revision_ids[] }
Asset { asset_id, version, sha256, media_type, width?, height?, duration_ticks?,
        storage_uri, rights_status, attribution, visibility, verification_status }
```
- 时间统一为整数帧 tick + fps 有理数，音频采样可在编译 RenderPlan 时转换，避免毫秒浮点累计误差。
- Clip 开始/结束严格验证，负区间、重叠的非法规则、未知 asset 和超限参数拒绝；按轨道 z-index 和作用域合成。
- UI 拖拽后保存 Canonical Timeline revision；FFmpeg 根据同一版本渲染，源数据和输出 hash 关联。
- 一旦接受新的 Timeline revision，旧版本保留只读用于回退，不能“保存即覆盖全部可追溯状态”。

## 初版支持的媒体能力
- 图片：缩放、平移、裁切、静态 Ken Burns、基本淡入淡出（不要实现完整复杂特效）。
- 视频：裁剪/缩放/长宽比填充、最基础转场、音频选择。
- 音频：上传、时长读取、音量、淡入淡出、基本混音。
- 字幕：SRT、可见字幕层、文本模板、精确时间与换行限制。
- 输出：720p/1080p 预设（按硬件负载选择默认）；横屏/竖屏；预设音视频编码与封装；失败任务保存日志。
- 优先在当前仓库已有 FFmpeg 实现之上重构，避免完全平行建设新的渲染引擎。

## 预览策略
- 浏览器低成本预览可以使用 img/video/canvas/CSS overlays；它不是精确最终渲染的证明。
- 引入 Rendiv 仅作为实验 POC，核实 Chromium frame capture 资源消耗、字体/字幕一致性、输出兼容性、持久化及替换成本。
- 默认正式渲染器：FFmpeg。若 Rendiv POC 没有明显工程收益，则不纳入核心依赖。
- 使用 `ffprobe`/decoder 对导出文件进行验证，不能只检查文件路径存在。

## 媒体资产安全
- 上传后做 type sniff、大小上限、分辨率/时长上限、沙箱解码测试；不依赖文件扩展名判断。
- 存储文件名由服务端生成、hash 检查，避免路径遍历和同名覆盖；对象可独立设置 private/public。
- 从 URL 导入素材使用 allowlist / IP 范围阻断 / 端口/重定向检查，以防 SSRF。
- 导出默认 PRIVATE，只有拥有访问权的用户可访问；过期清理采用数据库引用计数/延迟删除和审计，不清除用户原有素材。

## 验收案例
- 3 张图片 + 1 音频 + SRT：出片通过 `ffprobe`，输出时长符合时间轴 ±容忍误差。
- 混合图片/已有 MP4、两轨音乐/人声、一个场景修改后只重算相关合成任务。
- 改变 fps/分辨率后旧缓存不误用。
- 任务取消/进程重启后文件不会被误标为成功；半成品保留为不可发布。
- 字幕中有非 ASCII 中文，字体、行距、换行、SRT 下载可用。
