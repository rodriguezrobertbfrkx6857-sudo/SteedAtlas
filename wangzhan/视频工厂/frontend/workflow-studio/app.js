const STORAGE_KEY = "baiqipu-video-factory-workflow-v10";
const AUTH_STORAGE_KEY = "auth-storage";
const WORKFLOW_API_BASE = "/api/v1/video/workflow";
const HORSE_RAG_API = "/api/v1/horses/rag-library";
const NODE_WIDTH = 205;
const NODE_HEIGHT = 150;
const CANVAS_WIDTH = 1680;
const CANVAS_HEIGHT = 860;
const TASK_POLL_MS = 2500;
const NODE_SEQUENCE = [
  "reference_input",
  "reference_analyze",
  "input",
  "script",
  "storyboard",
  "voice",
  "keyframe",
  "subtitle",
  "veo",
  "compose",
  "output",
  "xhs_publish",
];
const CONNECTION_LANE_OFFSETS = {
  "e-script-subtitle": { sourceY: 34, targetY: -34, curveFactor: 0.5, emphasize: true },
  "e-subtitle-compose": { sourceY: -34, targetY: 34, curveFactor: 0.5, emphasize: true },
};

const fallbackHorseImages = {
  "赤兔": "../images/chitu.png",
  "乌骓": "../images/wuzhui.png",
  "的卢": "../images/dilu.png",
  "汗血": "../images/hanxue.png",
  "绝影": "../images/jueying.png",
};
const horseImages = { ...fallbackHorseImages };
const fallbackHorseOptions = Object.keys(fallbackHorseImages);
let horseRagProfiles = [];

const BASE_VIDEO_TEMPLATE = {
  id: "ink-war-scroll",
  name: "水墨古战场卷轴基础模板",
  source: "vedio/dec20191fecada3542e5dbbef9bc5ba2.mp4",
  visualStyle: "水墨古战场卷轴动画，纸本留白，灰绿色烟尘，墨黑烽烟，红色战旗点缀，远景士兵剪影，卷轴画框转场，骑马古代将领剪影，庄重史诗氛围",
  camera: "水墨画卷推进 / 战场横移 / 烟尘揭示 / 低角度骑马剪影",
  keyframePrompt: "用于 Veo 的 9:16 视频首尾帧，水墨古战场卷轴质感，主体清晰，马匹和主人完整可辨，运动方向明确，灰绿烟尘、红色战旗、纸本留白、远景人群剪影，电影分镜构图，无文字无水印，不照搬样片画面",
  motionPrompt: "保持水墨卷轴动画质感：烟尘缓慢流动，旗帜轻微飘动，画卷式横移推进，骑马剪影稳定自然，不要黑场开头或结尾",
};

const nodeMeta = {
  reference_input: { label: "参考素材上传", kind: "input", type: "参考", color: "cyan" },
  reference_analyze: { label: "参考风格分析", kind: "ai", type: "分析", color: "violet" },
  input: { label: "内容输入", kind: "input", type: "入口", color: "cyan" },
  script: { label: "剧本创作", kind: "ai", type: "文本", color: "violet" },
  storyboard: { label: "分镜拆解", kind: "text", type: "结构化", color: "amber" },
  keyframe: { label: "关键帧生成", kind: "image", type: "图片", color: "pink" },
  veo: { label: "视频片段生成", kind: "video", type: "视频", color: "blue" },
  voice: { label: "声音规划", kind: "audio", type: "音频", color: "green" },
  subtitle: { label: "字幕规划", kind: "text", type: "字幕", color: "amber" },
  compose: { label: "视频合成", kind: "video", type: "合成", color: "blue" },
  output: { label: "成片输出", kind: "output", type: "结果", color: "red" },
  xhs_publish: { label: "小红书自动发布", kind: "output", type: "发布", color: "red" },
};

const MODEL_FALLBACKS = {
  gpt: [
    "gpt-5.4",
    "gpt-5.5",
    "gpt-5.2",
    "gpt-4.1",
    "gpt-4.1-mini",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "gemini-3.1-pro-preview",
    "gemini-3-pro-preview-thinking",
  ],
  image: [
    "gpt-image-2",
    "gpt-image-2-all",
    "gpt-image-1.5",
    "gpt-4o-image",
    "grok-4-2-image",
    "jimeng-4.5",
    "jimeng-4.0",
    "midjourney",
    "chat_relax_imagine",
  ],
  veo: [
    "veo_3_1-fast-4K",
    "veo_3_1-fast",
    "veo_3_1-4K",
    "veo_3_1",
    "veo_3_0",
    "kling-3.0-omni-720p-noref-mute",
    "kling-3.0-omni-720p-noref-audio",
    "kling-3.0-omni-720p-ref-mute",
    "kling-3.0-omni-720p-ref-audio",
    "sora-2",
    "grok-video-3-10s",
  ],
};

const defaultWorkflow = {
  settings: {
    executionMode: "site-workflow",
    mode: "step-by-step",
    layoutVersion: 11,
  },
  nodes: [
    {
      id: "reference_input",
      type: "reference_input",
      x: 20,
      y: 44,
      status: "idle",
      progress: 0,
      fields: {
        enabled: "关闭",
        sourceType: "上传文件",
        mediaType: "unknown",
        mediaUrl: "",
        localPath: "",
        assets: [],
        subjectWeight: "60",
        styleWeight: "25",
        cameraWeight: "15",
        note: "可选：上传图片或视频作为风格参考",
      },
      output: null,
    },
    {
      id: "reference_analyze",
      type: "reference_analyze",
      x: 255,
      y: 44,
      status: "idle",
      progress: 0,
      fields: {
        model: "gpt-5.4",
        credentialRef: "server/.env: VIDEO_FACTORY_GPT_*",
        focus: "提取视觉风格、镜头语言、色彩和节奏",
      },
      output: null,
    },
    {
      id: "input",
      type: "input",
      x: 20,
      y: 300,
      status: "idle",
      progress: 0,
      fields: {
        horse: "赤兔",
        topic: "",
        brief: "",
        audience: "抖音 / 视频号历史国风内容",
        duration: "15",
        aspect: "9:16",
        runMode: "成片模式",
        videoCount: "1",
      },
      output: null,
    },
    {
      id: "script",
      type: "script",
      x: 255,
      y: 300,
      status: "idle",
      progress: 0,
      fields: {
        model: "gpt-5.4",
        credentialRef: "server/.env: VIDEO_FACTORY_GPT_*",
        style: "情绪叙事",
        jsonMode: "严格 JSON",
        temperature: "0.7",
        customPrompt: "输出适合短视频的强钩子、旁白、分镜和画面提示词。",
      },
      output: null,
    },
    {
      id: "storyboard",
      type: "storyboard",
      x: 490,
      y: 300,
      status: "idle",
      progress: 0,
      fields: {
        shotCount: "3",
        shotSeconds: "8",
        camera: BASE_VIDEO_TEMPLATE.camera,
        visualStyle: BASE_VIDEO_TEMPLATE.visualStyle,
        promptLanguage: "中文提示词",
        promptGuidance: `${BASE_VIDEO_TEMPLATE.name}：${BASE_VIDEO_TEMPLATE.visualStyle}。每个镜头都要服务同一个故事线，避免跳戏。`,
      },
      output: null,
    },
    {
      id: "keyframe",
      type: "keyframe",
      x: 725,
      y: 300,
      status: "idle",
      progress: 0,
      fields: {
        provider: "gpt-image-2",
        credentialRef: "server/.env: VIDEO_FACTORY_IMAGE_*",
        frameCount: "2",
        referenceMode: "首尾关键帧",
        imageSize: "9:16",
        apiSize: "1024x1792",
        consistency: "统一马匹、主人、服饰甲胄、战场空间、运动方向、光线色调；尾帧要能衔接下一镜首帧",
        promptStyle: BASE_VIDEO_TEMPLATE.keyframePrompt,
        customPrompt: BASE_VIDEO_TEMPLATE.keyframePrompt,
      },
      output: null,
    },
    {
      id: "veo",
      type: "veo",
      x: 960,
      y: 300,
      status: "idle",
      progress: 0,
      fields: {
        provider: "站内视频生成",
        model: "veo_3_1-fast-4K",
        credentialRef: "server/.env: VIDEO_FACTORY_VEO_*",
        generateAudio: "是",
        aspect: "9:16",
        quality: "auto",
        parallel: "3",
        motionPrompt: BASE_VIDEO_TEMPLATE.motionPrompt,
        negativePrompt: "低清晰度、错字、畸形、人物脸部崩坏",
      },
      output: null,
    },
    {
      id: "voice",
      type: "voice",
      x: 725,
      y: 44,
      status: "idle",
      progress: 0,
      fields: {
        mode: "中文配音优先",
        engine: "中文配音 + 原生声音备用",
        voice: "zh-CN-YunxiNeural",
        speed: "1.0",
        emotion: "庄重 / 热血",
        soundscape: "马蹄声、战场风声、低沉鼓点、电影感环境声",
        format: "mp3",
      },
      output: null,
    },
    {
      id: "subtitle",
      type: "subtitle",
      x: 725,
      y: 556,
      status: "idle",
      progress: 0,
      fields: {
        mode: "仅站内 SRT",
        style: "金色下三分之一",
        language: "简体中文",
        maxChars: "18",
        position: "底部居中",
        bilingual: "否",
      },
      output: null,
    },
    {
      id: "compose",
      type: "compose",
      x: 1195,
      y: 300,
      status: "idle",
      progress: 0,
      fields: {
        engine: "站内合成",
        transition: "卷轴擦除",
        bgm: "史诗鼓点",
        ducking: "自动压低背景乐",
        cover: "自动抽帧封面",
      },
      output: null,
    },
    {
      id: "output",
      type: "output",
      x: 1430,
      y: 300,
      status: "idle",
      progress: 0,
      fields: {
        saveTo: "网站 generated/videos",
        callback: "/api/v1/video/workflow/tasks",
        notify: "更新视频工厂历史任务",
        publish: "仅保存",
      },
      output: null,
    },
    {
      id: "xhs_publish",
      type: "xhs_publish",
      x: 1430,
      y: 44,
      status: "idle",
      progress: 0,
      fields: {
        enabled: "关闭",
        cookiePath: "",
        title: "",
        content: "",
        tags: "",
        visibility: "公开可见",
        baseUrl: "",
        publishPath: "",
        publishMode: "draft",
        scheduledAt: "",
        rollbackOnFail: "warn",
        autoCommentEnabled: "关闭",
        autoCommentText: "",
        autoCommentDelaySeconds: "0",
        autoCommentPath: "",
        collectCommentsEnabled: "关闭",
        collectCommentsLimit: "20",
        collectCommentsIncludeReplies: "关闭",
        collectCommentsPath: "",
        note: "可选：开启后，成片输出结束自动推送到小红书 MCP",
      },
      output: null,
    },
  ],
  connections: [
    { id: "e-reference-input-analyze", from: "reference_input", to: "reference_analyze", status: "idle" },
    { id: "e-reference-analyze-script", from: "reference_analyze", to: "script", status: "idle" },
    { id: "e-input-script", from: "input", to: "script", status: "idle" },
    { id: "e-script-storyboard", from: "script", to: "storyboard", status: "idle" },
    { id: "e-storyboard-keyframe", from: "storyboard", to: "keyframe", status: "idle" },
    { id: "e-keyframe-veo", from: "keyframe", to: "veo", status: "idle" },
    { id: "e-script-voice", from: "script", to: "voice", status: "idle" },
    { id: "e-script-subtitle", from: "script", to: "subtitle", status: "idle" },
    { id: "e-veo-compose", from: "veo", to: "compose", status: "idle" },
    { id: "e-voice-compose", from: "voice", to: "compose", status: "idle" },
    { id: "e-subtitle-compose", from: "subtitle", to: "compose", status: "idle" },
    { id: "e-compose-output", from: "compose", to: "output", status: "idle" },
    { id: "e-output-xhs", from: "output", to: "xhs_publish", status: "idle" },
  ],
};

const fieldDefs = {
  reference_input: [
    { key: "enabled", label: "参考流程开关", type: "select", options: ["关闭", "开启"] },
    { key: "sourceType", label: "素材来源", type: "select", options: ["上传文件", "URL"] },
    { key: "mediaUrl", label: "素材地址", type: "text", placeholder: "上传后自动填充，或手动粘贴 URL" },
    { key: "mediaType", label: "素材类型", type: "select", options: ["unknown", "image", "video"] },
    { key: "localPath", label: "本地路径", type: "text", placeholder: "上传后自动填充" },
    { key: "subjectWeight", label: "主体权重", type: "select", options: ["40", "50", "60", "70"] },
    { key: "styleWeight", label: "风格权重", type: "select", options: ["10", "20", "25", "30", "40"] },
    { key: "cameraWeight", label: "镜头权重", type: "select", options: ["10", "15", "20", "30"] },
    { key: "note", label: "说明", type: "textarea", placeholder: "可选：补充参考素材用途" },
  ],
  reference_analyze: [
    { key: "model", label: "模型选择", type: "select", modelSource: "gpt", options: MODEL_FALLBACKS.gpt },
    { key: "credentialRef", label: "站内配置", type: "text", help: "使用视频工厂的站内配置。" },
    { key: "focus", label: "分析重点", type: "textarea", placeholder: "例如：风格、镜头、色彩、节奏、人物一致性" },
  ],
  input: [
    { key: "horse", label: "主角名马", type: "select", options: ["赤兔", "乌骓", "的卢", "汗血", "绝影"] },
    { key: "topic", label: "视频主题", type: "text", placeholder: "例如：赤兔马为什么成为忠义象征" },
    { key: "brief", label: "内容补充", type: "textarea", placeholder: "补充你想强调的角度、平台或受众情绪。" },
    { key: "audience", label: "发布场景", type: "text" },
    {
      key: "runMode",
      label: "制作模式",
      type: "select",
      options: ["快速预览", "成片模式"],
      help: "快速预览会自动压低分镜、片段和关键帧数量；成片模式保持高质量长视频配置。",
    },
    { key: "duration", label: "目标时长", type: "select", options: ["15", "30", "60"] },
    { key: "aspect", label: "画幅", type: "select", options: ["9:16", "16:9", "1:1"] },
    { key: "videoCount", label: "生成视频数量", type: "select", options: ["1", "3", "5", "10"] },
  ],
  script: [
    { key: "model", label: "模型选择", type: "select", modelSource: "gpt", options: MODEL_FALLBACKS.gpt },
    { key: "credentialRef", label: "站内配置", type: "text", help: "配置由站内统一维护。" },
    { key: "style", label: "脚本风格", type: "select", options: ["情绪叙事", "知识讲述", "热血激励", "商业转化"] },
    { key: "jsonMode", label: "输出格式", type: "select", options: ["严格 JSON", "自然语言草稿"] },
    { key: "temperature", label: "创造度", type: "select", options: ["0.3", "0.5", "0.7", "0.9"] },
    { key: "customPrompt", label: "剧本要求补充", type: "textarea", placeholder: "补充口吻、节奏、重点情绪，会进入剧本和分镜。" },
  ],
  storyboard: [
    { key: "shotCount", label: "分镜数量", type: "select", options: ["1", "2", "3", "4", "5", "6", "8"] },
    { key: "shotSeconds", label: "单镜时长", type: "select", options: ["4", "5", "6", "8"] },
    { key: "camera", label: "镜头运动", type: "text" },
    { key: "visualStyle", label: "画面风格", type: "text" },
    { key: "promptLanguage", label: "画面描述语言", type: "select", options: ["中文提示词", "英文提示词", "中英双语"] },
    { key: "promptGuidance", label: "分镜要求补充", type: "textarea", placeholder: "补充镜头节奏、场景顺序、人物关系等约束。" },
  ],
  keyframe: [
    { key: "provider", label: "图片模型", type: "select", modelSource: "image", options: MODEL_FALLBACKS.image },
    { key: "credentialRef", label: "站内配置", type: "text", help: "图片制作配置由站内统一维护。" },
    { key: "frameCount", label: "关键帧数量", type: "select", options: ["1", "2", "3", "4", "5", "6", "8"] },
    { key: "referenceMode", label: "参考方式", type: "select", options: ["1 张风格锚点图复用", "每个分镜 1 张关键帧", "首尾关键帧", "主视觉统一参考图"] },
    { key: "imageSize", label: "图片画幅", type: "select", options: ["9:16", "16:9", "1:1"] },
    { key: "apiSize", label: "图片输出尺寸", type: "text", help: "例如 1024x1792。登录后会自动同步站内图片尺寸配置。" },
    { key: "consistency", label: "一致性约束", type: "textarea" },
    { key: "promptStyle", label: "图片风格", type: "text" },
    { key: "customPrompt", label: "图片要求补充", type: "textarea", placeholder: "补充人物、服饰、构图和风格要求，会进入关键帧生成。" },
  ],
  veo: [
    { key: "provider", label: "视频配置", type: "text" },
    { key: "model", label: "模型选择", type: "select", modelSource: "veo", options: MODEL_FALLBACKS.veo },
    { key: "credentialRef", label: "站内配置", type: "text" },
    { key: "generateAudio", label: "原生声音", type: "select", options: ["是", "否"] },
    { key: "aspect", label: "生成画幅", type: "select", options: ["9:16", "16:9"] },
    { key: "quality", label: "质量档位", type: "select", options: ["auto", "standard", "high"] },
    { key: "parallel", label: "片段数量", type: "select", options: ["1", "2", "3"] },
    { key: "motionPrompt", label: "运动要求", type: "textarea", placeholder: "补充镜头运动、主体稳定性、动作连续性要求。" },
    { key: "negativePrompt", label: "避让内容", type: "textarea" },
  ],
  voice: [
    { key: "mode", label: "处理方式", type: "select", options: ["中文配音优先", "原生声音优先", "本地配音备用", "仅规划不生成"] },
    { key: "engine", label: "语音引擎", type: "text" },
    { key: "voice", label: "音色", type: "text" },
    { key: "speed", label: "语速", type: "select", options: ["0.85", "1.0", "1.1", "1.2"] },
    { key: "emotion", label: "情绪", type: "text" },
    { key: "soundscape", label: "声音场景", type: "textarea" },
    { key: "format", label: "格式", type: "select", options: ["mp3", "wav"] },
  ],
  subtitle: [
    { key: "mode", label: "处理方式", type: "select", options: ["仅站内 SRT", "仅规划不生成"] },
    { key: "style", label: "字幕样式", type: "select", options: ["金色下三分之一", "战报横幅", "简洁白字", "月光题咏"] },
    { key: "language", label: "语言", type: "select", options: ["简体中文", "中英双语", "英文"] },
    { key: "maxChars", label: "每行字数", type: "select", options: ["14", "18", "22"] },
    { key: "position", label: "位置", type: "select", options: ["底部居中", "左下角", "中下方"] },
    { key: "bilingual", label: "双语字幕", type: "select", options: ["否", "是"] },
  ],
  compose: [
    { key: "engine", label: "合成引擎", type: "text" },
    { key: "transition", label: "转场", type: "select", options: ["卷轴擦除", "淡入淡出", "横向推镜", "镜门开启"] },
    { key: "bgm", label: "背景音乐", type: "select", options: ["史诗鼓点", "国风器乐", "沉静氛围", "不添加"] },
    { key: "ducking", label: "混音", type: "select", options: ["自动压低背景乐", "旁白优先", "音乐优先"] },
    { key: "cover", label: "封面", type: "select", options: ["自动抽帧封面", "第一帧", "自定义上传"] },
  ],
  output: [
    { key: "saveTo", label: "保存位置", type: "text" },
    { key: "callback", label: "任务回传", type: "text" },
    { key: "notify", label: "完成动作", type: "text" },
    { key: "publish", label: "发布方式", type: "select", options: ["仅保存", "保存并加入历史", "保存并待发布"] },
  ],
  xhs_publish: [
    {
      key: "enabled",
      label: "自动发布开关",
      type: "select",
      options: ["关闭", "开启"],
      help: "默认建议先关闭。先跑通视频生成与下载，再开启自动发布。",
    },
    {
      key: "cookiePath",
      label: "Cookies 文件路径",
      type: "text",
      placeholder: "例如：D:\\xhs\\cookies.json",
      help: "建议先在浏览器登录小红书后导出 cookies.json，这里填写绝对路径。",
    },
    {
      key: "title",
      label: "发布标题",
      type: "text",
      placeholder: "留空则使用任务标题",
      help: "建议 12~20 字，避免特殊符号过多。",
    },
    {
      key: "content",
      label: "发布文案",
      type: "textarea",
      placeholder: "留空则使用默认文案",
      help: "建议先简短，确认流程稳定后再扩展长文案。",
    },
    {
      key: "tags",
      label: "标签",
      type: "text",
      placeholder: "多个标签用逗号分隔",
      help: "示例：战马,历史,短片；不要带 #。",
    },
    {
      key: "visibility",
      label: "可见范围",
      type: "select",
      options: ["公开可见", "仅自己可见", "仅粉丝可见"],
      help: "首轮联调建议选“仅自己可见”。",
    },
    {
      key: "publishMode",
      label: "发布模式",
      type: "select",
      options: ["direct", "draft", "scheduled"],
      help: "direct=直接发布，draft=仅存草稿，scheduled=定时发布。",
    },
    {
      key: "scheduledAt",
      label: "定时发布时间",
      type: "text",
      placeholder: "例如：2026-05-11T20:30:00+08:00",
      help: "仅 publishMode=scheduled 生效，建议 ISO 时间（含时区）。",
    },
    {
      key: "rollbackOnFail",
      label: "失败回滚策略",
      type: "select",
      options: ["off", "warn", "rollback"],
      help: "off=不处理，warn=提示，rollback=失败后给回滚提示。",
    },
    {
      key: "autoCommentEnabled",
      label: "自动评论",
      type: "select",
      options: ["关闭", "开启"],
      help: "发布成功后自动评论（建议先草稿模式联调）。",
    },
    {
      key: "autoCommentText",
      label: "评论内容",
      type: "textarea",
      placeholder: "例如：感谢观看，欢迎留言交流。",
      help: "留空将使用站内默认评论文案。",
    },
    {
      key: "autoCommentDelaySeconds",
      label: "评论延迟秒数",
      type: "select",
      options: ["0", "5", "10", "30", "60"],
      help: "评论动作延迟处理。",
    },
    {
      key: "autoCommentPath",
      label: "评论路径配置",
      type: "text",
      placeholder: "为空则使用 server/.env 默认值",
      help: "例如：/api/v1/comment/create",
    },
    {
      key: "collectCommentsEnabled",
      label: "采集评论",
      type: "select",
      options: ["关闭", "开启"],
      help: "发布后自动拉取评论数据。",
    },
    {
      key: "collectCommentsLimit",
      label: "采集条数",
      type: "select",
      options: ["10", "20", "50", "100"],
      help: "每次最多采集的评论条数。",
    },
    {
      key: "collectCommentsIncludeReplies",
      label: "包含回复",
      type: "select",
      options: ["关闭", "开启"],
      help: "开启后尝试同时抓取评论回复。",
    },
    {
      key: "collectCommentsPath",
      label: "评论采集路径",
      type: "text",
      placeholder: "为空则使用 server/.env 默认值",
      help: "例如：/api/v1/comment/list",
    },
    {
      key: "baseUrl",
      label: "发布服务地址",
      type: "text",
      placeholder: "为空则使用 server/.env",
      help: "例如：http://127.0.0.1:9000（不要以 / 结尾）。",
    },
    {
      key: "publishPath",
      label: "发布路径配置",
      type: "text",
      placeholder: "为空则使用 server/.env",
      help: "例如：/api/publish/xiaohongshu。",
    },
    {
      key: "note",
      label: "说明",
      type: "textarea",
      placeholder: "可选：发布策略备注",
      help: "可记录账号、发布时间窗口、风控策略。",
    },
  ],
};

const PARAMETER_PRESETS = [
  {
    id: "single-shot-test",
    name: "单分镜测试",
    desc: "低成本快速验证主题、画面和声音方向。",
    accent: "cyan",
    patches: {
      input: { runMode: "快速预览", duration: "15", videoCount: "1" },
      storyboard: { shotCount: "1", shotSeconds: "4" },
      keyframe: { frameCount: "2", referenceMode: "首尾关键帧" },
      veo: { parallel: "1", quality: "standard", generateAudio: "是" },
      subtitle: { maxChars: "14", style: "简洁白字", language: "简体中文" },
      compose: { bgm: "不添加", transition: "淡入淡出" },
    },
  },
  {
    id: "three-shot-long",
    name: "三分镜长视频",
    desc: "三段连贯生成并合成长视频，适合正式验证长片。",
    accent: "blue",
    patches: {
      input: { runMode: "成片模式", duration: "30", videoCount: "1" },
      storyboard: { shotCount: "3", shotSeconds: "8" },
      keyframe: { frameCount: "2", referenceMode: "首尾关键帧" },
      veo: { parallel: "3", quality: "high", generateAudio: "是" },
      subtitle: { maxChars: "14", style: "金色下三分之一", language: "简体中文" },
      compose: { bgm: "史诗鼓点", transition: "卷轴擦除" },
    },
  },
  {
    id: "xhs-koubo",
    name: "小红书爆款口播",
    desc: "强开头、口语化旁白、短字幕，适合种草式历史口播。",
    accent: "pink",
    patches: {
      input: { runMode: "成片模式", duration: "30", videoCount: "1", audience: "小红书历史口播" },
      script: {
        style: "情绪叙事",
        temperature: "0.7",
        customPrompt: "前3秒必须有强钩子，旁白使用中文口语，句子短，节奏紧，结尾留一个可评论的问题。",
      },
      storyboard: { shotCount: "3", shotSeconds: "8" },
      voice: { mode: "中文配音优先", speed: "1.1", emotion: "口语、利落、有停顿" },
      subtitle: { maxChars: "14", style: "简洁白字", language: "简体中文" },
      veo: { parallel: "3", quality: "high", generateAudio: "是" },
      output: { publish: "保存并待发布" },
      xhs_publish: { publishMode: "draft", visibility: "仅自己可见" },
    },
  },
  {
    id: "cinematic-epic",
    name: "电影感史诗",
    desc: "画面更重氛围和镜头连续性，适合正式成片。",
    accent: "amber",
    patches: {
      input: { runMode: "成片模式", duration: "30", videoCount: "1" },
      storyboard: {
        shotCount: "3",
        shotSeconds: "8",
        camera: "低角度推进 / 横移跟拍 / 烟尘揭示 / 史诗远景",
        visualStyle: "电影感古战场、厚重光影、写实盔甲、烟尘、旌旗、统一主角形象",
      },
      keyframe: {
        frameCount: "2",
        referenceMode: "首尾关键帧",
        consistency: "统一马匹、主人、服饰、色调、时代和战场空间",
      },
      veo: { parallel: "3", quality: "high", generateAudio: "是" },
      voice: { emotion: "庄重 / 热血", speed: "1.0" },
      subtitle: { style: "月光题咏", maxChars: "18", language: "简体中文" },
      compose: { bgm: "史诗鼓点", transition: "镜门开启" },
    },
  },
  {
    id: "two-shot-preview",
    name: "双分镜预览",
    desc: "比单分镜更接近成片，但成本和等待时间仍然可控。",
    accent: "cyan",
    patches: {
      input: { runMode: "快速预览", duration: "16", videoCount: "1" },
      storyboard: { shotCount: "2", shotSeconds: "6" },
      keyframe: { frameCount: "2", referenceMode: "首尾关键帧" },
      veo: { parallel: "2", quality: "standard", generateAudio: "是" },
      subtitle: { maxChars: "14", style: "简洁白字", language: "简体中文" },
      compose: { bgm: "史诗鼓点", transition: "卷轴擦除" },
    },
  },
  {
    id: "five-shot-epic",
    name: "五分镜史诗长片",
    desc: "更完整的起承转合，适合正式长视频和故事感强的名马主题。",
    accent: "amber",
    patches: {
      input: { runMode: "成片模式", duration: "45", videoCount: "1" },
      script: {
        style: "史诗叙事",
        temperature: "0.65",
        customPrompt: "写成一条完整的英雄史诗短片，强调命运转折、人物选择和名马精神。旁白必须是中文口语，但保留古风质感。",
      },
      storyboard: {
        shotCount: "5",
        shotSeconds: "8",
        camera: "卷轴展开 / 低角度冲锋 / 人马并肩 / 战场远景 / 片尾定格",
      },
      keyframe: {
        frameCount: "2",
        referenceMode: "首尾关键帧",
        consistency: "每镜首帧承接上一镜尾帧，马匹、主人、甲胄、战场方向和光影必须统一",
      },
      veo: { parallel: "3", quality: "high", generateAudio: "是" },
      voice: { emotion: "庄重 / 热血", speed: "1.0" },
      subtitle: { style: "金色下三分之一", maxChars: "18", language: "简体中文" },
      compose: { bgm: "史诗鼓点", transition: "卷轴擦除" },
    },
  },
  {
    id: "rag-biography",
    name: "知识库传记",
    desc: "优先参考名马知识库，适合做马与主人一生故事。",
    accent: "blue",
    patches: {
      input: { runMode: "成片模式", duration: "30", videoCount: "1", audience: "历史人物传记 / 名马故事" },
      script: {
        style: "人物传记",
        temperature: "0.55",
        customPrompt: "必须优先使用知识库中的马的一生、主人的一生和关键战役。叙事要具体，不要泛泛而谈，结尾点出名马精神。",
      },
      storyboard: { shotCount: "3", shotSeconds: "8" },
      keyframe: { frameCount: "2", referenceMode: "首尾关键帧" },
      veo: { parallel: "3", quality: "high", generateAudio: "是" },
      subtitle: { maxChars: "18", style: "金色下三分之一", language: "简体中文" },
    },
  },
  {
    id: "batch-three-variants",
    name: "批量三条测试",
    desc: "一次生成三条不同脚本版本，用来挑选方向。",
    accent: "pink",
    patches: {
      input: { runMode: "快速预览", duration: "15", videoCount: "3" },
      script: {
        style: "短视频钩子",
        temperature: "0.85",
        customPrompt: "每一条脚本必须有不同切入点，不能只是换句子。分别尝试悬念、情绪、反转三种开头。",
      },
      storyboard: { shotCount: "1", shotSeconds: "4" },
      keyframe: { frameCount: "2", referenceMode: "首尾关键帧" },
      veo: { parallel: "1", quality: "standard", generateAudio: "是" },
      subtitle: { maxChars: "14", style: "简洁白字", language: "简体中文" },
    },
  },
  {
    id: "visual-poetry",
    name: "水墨纯画面",
    desc: "减少口播压力，强化画卷、水墨、战场氛围和音乐节奏。",
    accent: "green",
    patches: {
      input: { runMode: "成片模式", duration: "24", videoCount: "1" },
      script: {
        style: "诗意旁白",
        temperature: "0.62",
        customPrompt: "旁白极短，只保留关键句。画面提示词要更具体，突出水墨卷轴、马匹动作、战场空间和情绪变化。",
      },
      storyboard: { shotCount: "3", shotSeconds: "8" },
      keyframe: { frameCount: "2", referenceMode: "首尾关键帧" },
      veo: { parallel: "3", quality: "high", generateAudio: "是" },
      voice: { emotion: "克制 / 诗意", speed: "0.95" },
      subtitle: { maxChars: "12", style: "极简底部字幕", language: "简体中文" },
      compose: { bgm: "低沉鼓点与箫声", transition: "水墨晕染" },
    },
  },
];

let workflow = loadWorkflow();
let selectedId = "reference_input";
let zoom = 1;
let autoFitZoom = true;
let panX = 0;
let panY = 0;
let isRunning = false;
let runToken = 0;
let activeTask = null;
let activeTaskId = null;
let taskPollTimer = null;
let lastTaskSignature = "";
let tasks = [];
let downloadedTaskId = "";
let providerStatus = null;
let providerModels = null;
let batchRunState = null;
let generatedVideos = [];
let selectedGeneratedTaskId = "";
let nodeOutputHistory = {};
let expandedBriefNodeIds = new Set();
let selectedPresetId = "";
let batchQueueOptions = { skipFailed: false };
let canvasFocusFrame = 0;

const els = {
  nodeList: document.querySelector("#nodeList"),
  nodesLayer: document.querySelector("#nodesLayer"),
  linkLayer: document.querySelector("#linkLayer"),
  canvasInner: document.querySelector("#canvasInner"),
  canvasViewport: document.querySelector("#canvasViewport"),
  inspectorContent: document.querySelector("#inspectorContent"),
  nodeCount: document.querySelector("#nodeCount"),
  linkCount: document.querySelector("#linkCount"),
  workflowStatus: document.querySelector("#workflowStatus"),
  payloadSummary: document.querySelector("#payloadSummary"),
  zoomLabel: document.querySelector("#zoomLabel"),
  runLog: document.querySelector("#runLog"),
  runTitle: document.querySelector("#runTitle"),
  previewImage: document.querySelector("#previewImage"),
  previewVideo: document.querySelector("#previewVideo"),
  previewTitle: document.querySelector("#previewTitle"),
  previewHeadline: document.querySelector("#previewHeadline"),
  previewCaption: document.querySelector("#previewCaption"),
  previewStatus: document.querySelector("#previewStatus"),
  previewAspect: document.querySelector("#previewAspect"),
  generatedVideoMenu: document.querySelector("#generatedVideoMenu"),
  previewEmpty: document.querySelector("#previewEmpty"),
  sceneStrip: document.querySelector("#sceneStrip"),
  jsonDialog: document.querySelector("#jsonDialog"),
  jsonExport: document.querySelector("#jsonExport"),
  taskList: document.querySelector("#taskList"),
  executionTimeline: document.querySelector("#executionTimeline"),
  executionPulse: document.querySelector("#executionPulse"),
  runtimeEvents: document.querySelector("#runtimeEvents"),
  nodeBriefGrid: document.querySelector("#nodeBriefGrid"),
  downloadVideoBtn: document.querySelector("#downloadVideoBtn"),
  clearTaskHistoryBtn: document.querySelector("#clearTaskHistoryBtn"),
  runtimeBadge: document.querySelector("#runtimeBadge"),
  preflightPanel: document.querySelector("#preflightPanel"),
  errorCenter: document.querySelector("#errorCenter"),
  presetPanel: document.querySelector("#presetPanel"),
  canvasMinimap: document.querySelector("#canvasMinimap"),
  batchQueue: document.querySelector("#batchQueue"),
};

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function clampNodePositionValue(value, min, max, fallback) {
  const number = Number(value);
  const safe = Number.isFinite(number) ? number : Number(fallback);
  return Math.max(min, Math.min(max, safe));
}

function normalizeWorkflow(workflowValue) {
  const incoming = workflowValue && Array.isArray(workflowValue.nodes) && Array.isArray(workflowValue.connections)
    ? workflowValue
    : clone(defaultWorkflow);
  const next = clone(defaultWorkflow);
  const useDefaultLayout = Number(incoming.settings?.layoutVersion || 0) < Number(defaultWorkflow.settings.layoutVersion || 1);
  next.settings = { ...defaultWorkflow.settings, ...(next.settings || {}) };
  next.settings = { ...next.settings, ...(incoming.settings || {}) };
  next.settings.layoutVersion = defaultWorkflow.settings.layoutVersion;
  next.settings.executionMode = "site-workflow";
  next.nodes = next.nodes.map((defaultNode) => {
    const savedNode = incoming.nodes.find((node) => node.id === defaultNode.id) || {};
    const fields = { ...defaultNode.fields, ...(savedNode.fields || {}) };
    if (defaultNode.id === "script" && ["gpt-5.4-mini", "gpt-mini", "gpt-mini-high"].includes(fields.model)) {
      fields.model = defaultNode.fields.model;
      fields.credentialRef = defaultNode.fields.credentialRef;
    }
    if (defaultNode.id === "keyframe" && ["图片生成 AI", "图像生成 AI", "image-ai"].includes(fields.provider)) {
      fields.provider = defaultNode.fields.provider;
      fields.credentialRef = defaultNode.fields.credentialRef;
    }
    if (defaultNode.id === "keyframe") {
      const mode = String(fields.referenceMode || "").trim();
      if (!mode || mode === "1 张风格锚点图复用") {
        fields.referenceMode = defaultNode.fields.referenceMode;
      }
      if (String(fields.referenceMode || "").trim() === "首尾关键帧" && (!fields.frameCount || String(fields.frameCount) === "1")) {
        fields.frameCount = "2";
      }
    }
    if (defaultNode.id === "veo" && ["veo-3.0-generate-001", "veo-3.0", "veo-3"].includes(fields.model)) {
      fields.model = defaultNode.fields.model;
      fields.credentialRef = defaultNode.fields.credentialRef;
    }
    const xValue = useDefaultLayout ? defaultNode.x : (savedNode.x ?? defaultNode.x);
    const yValue = useDefaultLayout ? defaultNode.y : (savedNode.y ?? defaultNode.y);
    return {
      ...defaultNode,
      ...savedNode,
      x: clampNodePositionValue(xValue, 16, CANVAS_WIDTH - NODE_WIDTH - 16, defaultNode.x),
      y: clampNodePositionValue(yValue, 16, CANVAS_HEIGHT - NODE_HEIGHT - 16, defaultNode.y),
      fields,
      status: "idle",
      progress: 0,
      output: null,
    };
  });
  next.connections = next.connections.map((defaultConnection) => {
    const savedConnection = incoming.connections.find((connection) => connection.id === defaultConnection.id) || {};
    return {
      ...defaultConnection,
      ...savedConnection,
      status: "idle",
    };
  });
  return next;
}

function loadWorkflow() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return normalizeWorkflow(clone(defaultWorkflow));
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.connections)) return normalizeWorkflow(clone(defaultWorkflow));
    return normalizeWorkflow(parsed);
  } catch {
    return normalizeWorkflow(clone(defaultWorkflow));
  }
}

function saveWorkflow() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(getWorkflowTemplate()));
  addLog("系统", "当前制作模板已保存到浏览器本地。");
}

function getWorkflowTemplate() {
  return {
    settings: { ...workflow.settings, executionMode: "site-workflow" },
    nodes: workflow.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      x: node.x,
      y: node.y,
      fields: { ...node.fields },
    })),
    connections: workflow.connections.map(({ id, from, to }) => ({ id, from, to })),
  };
}

function loadAuthState() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state ?? null;
  } catch {
    return null;
  }
}

function getAccessToken() {
  const state = loadAuthState();
  return state?.accessToken ?? state?.access_token ?? "";
}

function getRefreshToken() {
  const state = loadAuthState();
  return state?.refreshToken ?? state?.refresh_token ?? "";
}

function isAuthenticated() {
  const state = loadAuthState();
  return Boolean(
    state &&
      state.isAuthenticated &&
      (state.accessToken || state.access_token || state.refreshToken || state.refresh_token || state.user)
  );
}

function renderAuthLink() {
  const link = document.querySelector(".login-link");
  if (!link) return;
  if (isAuthenticated()) {
    link.textContent = "已登录";
    link.href = "#";
    link.classList.add("logged-in");
    link.title = "当前账号已登录";
    return;
  }
  link.textContent = "登录";
  link.href = "/login?next=%2Fvideo-factory";
  link.classList.remove("logged-in");
  link.title = "前往登录";
}

function saveAuthStatePatch(patch) {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    parsed.state = { ...(parsed.state || {}), ...patch };
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // Ignore malformed auth storage and let the next request ask for login.
  }
}

function clearAuthState() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return "";
  const response = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return "";
  const payload = await response.json();
  const accessToken = payload?.access_token || payload?.accessToken || "";
  if (accessToken) {
    saveAuthStatePatch({ accessToken, access_token: accessToken, isAuthenticated: true });
  }
  return accessToken;
}

async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${WORKFLOW_API_BASE}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body,
    credentials: "include",
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail =
      (payload && (payload.detail || payload.message)) ||
      `${response.status} ${response.statusText}`;
    if (response.status === 401 && !options.__retriedAuth) {
      const nextToken = await refreshAccessToken();
      if (nextToken) {
        return apiRequest(path, { ...options, __retriedAuth: true });
      }
      clearAuthState();
      throw new Error("登录已过期，请回到主站重新登录后再运行视频工厂。");
    }
    const error = new Error(String(detail));
    error.status = response.status;
    throw error;
  }

  return payload;
}

function horseOptionsFromRag() {
  const names = horseRagProfiles
    .map((item) => String(item?.name || "").trim())
    .filter(Boolean);
  const current = String(findNode("input")?.fields?.horse || "").trim();
  return [...new Set([...names, ...fallbackHorseOptions, current].filter(Boolean))];
}

function updateHorseSelectOptions() {
  const inputFields = fieldDefs.input || [];
  const horseField = inputFields.find((field) => field.key === "horse");
  if (!horseField) return;
  horseField.options = horseOptionsFromRag();
}

async function loadHorseRagLibrary({ silent = true } = {}) {
  try {
    const response = await fetch(`${HORSE_RAG_API}?size=200`, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    horseRagProfiles = items
      .map((item) => ({
        id: String(item?.id || "").trim(),
        name: String(item?.name || "").trim(),
        image: String(item?.image || item?.image_url || "").trim(),
        owner: String(item?.owner || item?.figure || "").trim(),
      }))
      .filter((item) => item.name);
    horseRagProfiles.forEach((item) => {
      if (item.image) horseImages[item.name] = item.image;
    });
    updateHorseSelectOptions();
    if (!silent) {
      addLog("名马资料", `已加载 ${horseRagProfiles.length || fallbackHorseOptions.length} 匹名马。`);
    }
    renderInspector();
    renderPreview();
  } catch (error) {
    updateHorseSelectOptions();
    if (!silent) {
      addLog("名马资料", `马库暂不可用，已使用默认 5 匹名马：${error.message || "请求失败"}`);
    }
  }
}

function syncProviderFields(status) {
  if (!status) return false;
  let changed = false;
  const setField = (nodeId, key, value) => {
    if (value === undefined || value === null || value === "") return;
    const node = findNode(nodeId);
    if (!node) return;
    if (String(node.fields[key] ?? "") !== String(value)) {
      node.fields[key] = String(value);
      changed = true;
    }
  };
  const setModelField = (nodeId, key, value) => {
    if (value === undefined || value === null || value === "") return;
    const node = findNode(nodeId);
    if (!node || node.fields?.__modelLocked === "1") return;
    setField(nodeId, key, value);
  };

  setModelField("script", "model", status.gpt?.model);
  setField("script", "credentialRef", "server/.env: VIDEO_FACTORY_GPT_*");
  setModelField("reference_analyze", "model", status.gpt?.model);
  setField("reference_analyze", "credentialRef", "server/.env: VIDEO_FACTORY_GPT_*");
  setModelField("keyframe", "provider", status.image?.model);
  setField("keyframe", "apiSize", status.image?.size);
  setField("keyframe", "credentialRef", "server/.env: VIDEO_FACTORY_IMAGE_*");
  setModelField("veo", "model", status.veo?.model);
  setField("veo", "credentialRef", "server/.env: VIDEO_FACTORY_VEO_*");
  setField("xhs_publish", "baseUrl", status.xhs?.baseUrl);
  setField("xhs_publish", "publishPath", status.xhs?.publishPath);
  setField("xhs_publish", "autoCommentPath", status.xhs?.autoCommentPath);
  setField("xhs_publish", "collectCommentsPath", status.xhs?.collectCommentsPath);
  setField("xhs_publish", "cookiePath", status.xhs?.cookiePath);
  setField("xhs_publish", "visibility", status.xhs?.defaultVisibility);
  setField("xhs_publish", "autoCommentText", status.xhs?.defaultCommentText);
  if (status.xhs?.defaultCommentLimit !== undefined && status.xhs?.defaultCommentLimit !== null) {
    setField("xhs_publish", "collectCommentsLimit", String(status.xhs.defaultCommentLimit));
  }
  if (typeof status.veo?.generateAudio === "boolean") {
    setField("veo", "generateAudio", status.veo.generateAudio ? "是" : "否");
  }
  return changed;
}

async function refreshProviderModels({ silent = true } = {}) {
  if (!getAccessToken()) return null;
  try {
    providerModels = await apiRequest("/provider-models");
    const recommended = false;
    if (!silent) {
      const total = ["gpt", "image", "veo"]
        .reduce((sum, key) => sum + (Array.isArray(providerModels?.[key]?.models) ? providerModels[key].models.length : 0), 0);
      const fallbackTotal = ["gpt", "image", "veo"].reduce((sum, key) => sum + (MODEL_FALLBACKS[key] || []).length, 0);
      addLog("模型列表", total ? `已从站内 baseurl 读取 ${total} 个可选模型。${recommended ? "成片模式已优先切到高质量 Veo。" : ""}` : `暂未从 baseurl 读取到模型，已显示 ${fallbackTotal} 个常用候选。`);
    }
    if (recommended) {
      render();
    } else {
      renderInspector();
      renderStats();
    }
    return providerModels;
  } catch (error) {
    if (!silent) {
      addLog("模型列表", error.message || "模型列表读取失败。");
    }
    return null;
  }
}

async function refreshProviderStatus({ silent = true } = {}) {
  if (!getAccessToken()) return;
  try {
    providerStatus = await apiRequest("/provider-status");
    const changed = syncProviderFields(providerStatus);
    if (!silent) {
      addLog("站内配置", providerStatus?.mode ? `已同步站内服务：${providerStatus.mode}` : "已同步站内服务。");
    }
    if (changed) {
      render();
    } else {
      renderStats();
      renderInspector();
      renderNodes();
    }
    void refreshProviderModels({ silent: true });
  } catch (error) {
    if (!silent) {
      addLog("站内配置", error.message || "无法读取站内服务配置。");
    }
  }
}

async function testXhsConnection() {
  if (!getAccessToken()) {
    addLog("小红书连接", "请先登录主站账号，再检查发布配置。");
    return;
  }
  await refreshProviderStatus({ silent: true });
  const status = providerStatus?.xhs || {};
  const cookieOk = Boolean(status.cookieConfigured);
  const serviceOk = Boolean(status.configured && status.baseUrl && status.publishPath);
  const message = [
    serviceOk ? "发布服务已配置" : "发布服务未完整配置",
    cookieOk ? "Cookie 文件已找到" : "Cookie 文件未找到或未填写",
    status.baseUrl || "",
  ]
    .filter(Boolean)
    .join(" / ");
  addLog("小红书连接", message);
  renderInspector();
}

function findNode(id) {
  return workflow.nodes.find((node) => node.id === id);
}

function nodeDisplayOrder(node) {
  const index = NODE_SEQUENCE.indexOf(node.id);
  return index >= 0 ? index : NODE_SEQUENCE.length;
}

function orderedNodes() {
  return [...workflow.nodes].sort((a, b) => nodeDisplayOrder(a) - nodeDisplayOrder(b));
}

function optionEnabled(value) {
  const text = String(value ?? "").trim().toLowerCase();
  return ["1", "true", "yes", "on", "enabled", "开启", "是"].includes(text);
}

function referenceFlowEnabled() {
  const node = findNode("reference_input");
  return optionEnabled(node?.fields?.enabled);
}

function xhsPublishEnabled() {
  const node = findNode("xhs_publish");
  return optionEnabled(node?.fields?.enabled);
}

function preflightLevelRank(level) {
  return { error: 3, warn: 2, ok: 1 }[level] || 1;
}

function buildPreflightChecks() {
  const input = findNode("input");
  const reference = findNode("reference_input");
  const xhs = findNode("xhs_publish");
  const storyboard = findNode("storyboard");
  const veo = findNode("veo");
  const topic = String(input?.fields?.topic || "").trim();
  const shotCount = parsePositiveInt(storyboard?.fields?.shotCount || "1", 1);
  const shotSeconds = parsePositiveInt(storyboard?.fields?.shotSeconds || "8", 8);
  const videoCount = targetVideoCount();
  const providers = ["gpt", "image", "veo"].map((key) => ({
    key,
    ready: Boolean(providerStatus?.[key]?.configured),
    model: providerStatus?.[key]?.model || "",
  }));
  const checks = [
    {
      id: "login",
      level: getAccessToken() ? "ok" : "error",
      title: "登录状态",
      detail: getAccessToken() ? "已登录，可以创建工作流任务。" : "未登录，无法创建工作流任务。",
      nodeId: "",
    },
    {
      id: "topic",
      level: topic ? "ok" : "error",
      title: "视频主题",
      detail: topic ? compactText(topic, 86) : "内容输入节点还没有视频主题。",
      nodeId: "input",
    },
    ...providers.map((item) => ({
      id: `provider-${item.key}`,
      level: item.ready ? "ok" : providerStatus ? "error" : "warn",
      title: `${item.key.toUpperCase()} API`,
      detail: item.ready
        ? `已配置 ${item.model || "模型"}`
        : providerStatus
          ? "站内 API 配置未就绪，请检查 server/.env。"
          : "等待同步站内 API 状态。",
      nodeId: item.key === "gpt" ? "script" : item.key === "image" ? "keyframe" : "veo",
    })),
    {
      id: "duration",
      level: shotCount * shotSeconds <= Number(input?.fields?.duration || 30) + 8 ? "ok" : "warn",
      title: "时长与分镜",
      detail: `${shotCount} 镜 × ${shotSeconds}s，目标 ${input?.fields?.duration || 30}s。`,
      nodeId: "storyboard",
    },
    {
      id: "batch",
      level: videoCount > 3 ? "warn" : "ok",
      title: "批量数量",
      detail: videoCount > 1 ? `将按顺序生成 ${videoCount} 条视频。` : "单条视频制作。",
      nodeId: "input",
    },
    {
      id: "reference",
      level:
        referenceFlowEnabled() && !(reference?.fields?.mediaUrl || reference?.fields?.localPath)
          ? "warn"
          : "ok",
      title: "参考素材",
      detail:
        referenceFlowEnabled() && !(reference?.fields?.mediaUrl || reference?.fields?.localPath)
          ? "参考流程已开启，但还没有素材地址或本地路径。"
          : referenceFlowEnabled()
            ? "参考素材流程已开启。"
            : "参考素材流程关闭，不影响默认生成。",
      nodeId: "reference_input",
    },
    {
      id: "xhs",
      level:
        xhsPublishEnabled() && !(providerStatus?.xhs?.cookieConfigured || xhs?.fields?.cookiePath)
          ? "warn"
          : "ok",
      title: "小红书发布",
      detail:
        xhsPublishEnabled() && !(providerStatus?.xhs?.cookieConfigured || xhs?.fields?.cookiePath)
          ? "发布节点已开启，但 Cookie 尚未确认，视频生成不受影响。"
          : xhsPublishEnabled()
            ? "发布节点已开启，完成后会尝试推送。"
            : "发布节点关闭，仅生成和保存视频。",
      nodeId: "xhs_publish",
    },
    {
      id: "veo-parallel",
      level: Number(veo?.fields?.parallel || 1) > 3 ? "warn" : "ok",
      title: "Veo 并发",
      detail: `当前并发 ${veo?.fields?.parallel || 1} 段，模式 ${currentRunMode()}。`,
      nodeId: "veo",
    },
  ];
  return checks.sort((a, b) => preflightLevelRank(b.level) - preflightLevelRank(a.level));
}

function preflightBlockingIssues(checks = buildPreflightChecks()) {
  return checks.filter((item) => item.level === "error");
}

function renderPreflightPanel(checks = buildPreflightChecks()) {
  if (!els.preflightPanel) return;
  const errors = checks.filter((item) => item.level === "error").length;
  const warnings = checks.filter((item) => item.level === "warn").length;
  const topItems = checks.slice(0, 5);
  els.preflightPanel.innerHTML = `
    <div class="diagnostic-head">
      <div>
        <div class="section-heading">运行前体检</div>
        <strong>${errors ? `${errors} 项需要处理` : warnings ? `${warnings} 项建议确认` : "可以运行"}</strong>
      </div>
      <span class="diagnostic-score ${errors ? "error" : warnings ? "warn" : "ok"}">${errors ? "阻断" : warnings ? "提醒" : "通过"}</span>
    </div>
    <div class="diagnostic-list">
      ${topItems
        .map(
          (item) => `
            <button class="diagnostic-item ${item.level}" type="button" ${item.nodeId ? `data-error-node="${escapeHtml(item.nodeId)}"` : ""}>
              <span>${escapeHtml(item.title)}</span>
              <strong>${escapeHtml(compactText(item.detail, 92))}</strong>
            </button>
          `
        )
        .join("")}
    </div>
  `;
}

function collectWorkflowIssues() {
  const issues = [];
  if (activeTask?.error_message) {
    issues.push({
      level: "error",
      title: "任务错误",
      detail: activeTask.error_message,
      nodeId: activeTask.current_node || "",
    });
  }
  workflow.nodes.forEach((node) => {
    const hint = nodeFailureHint(node);
    if (!hint) return;
    issues.push({
      level: hint.level === "failed" ? "error" : "warn",
      title: nodeMeta[node.type]?.label || node.id,
      detail: hint.message || hint.chip,
      nodeId: node.id,
    });
  });
  buildPreflightChecks()
    .filter((item) => item.level !== "ok")
    .forEach((item) => {
      issues.push({
        level: item.level === "error" ? "error" : "warn",
        title: item.title,
        detail: item.detail,
        nodeId: item.nodeId,
      });
    });
  return issues.slice(0, 8);
}

function renderErrorCenter() {
  if (!els.errorCenter) return;
  const issues = collectWorkflowIssues();
  const errors = issues.filter((item) => item.level === "error").length;
  const warnings = issues.filter((item) => item.level === "warn").length;
  if (!issues.length) {
    els.errorCenter.innerHTML = `
      <div class="diagnostic-head">
        <div>
          <div class="section-heading">错误中心</div>
          <strong>暂无问题</strong>
        </div>
        <span class="diagnostic-score ok">清爽</span>
      </div>
      <div class="diagnostic-empty">如果某个节点失败、空输出或配置缺失，会在这里集中显示。</div>
    `;
    return;
  }
  els.errorCenter.innerHTML = `
    <div class="diagnostic-head">
      <div>
        <div class="section-heading">错误中心</div>
        <strong>${errors} 错误 / ${warnings} 提醒</strong>
      </div>
      <span class="diagnostic-score ${errors ? "error" : "warn"}">${errors ? "需处理" : "可继续"}</span>
    </div>
    <div class="diagnostic-list">
      ${issues
        .map(
          (item) => `
            <button class="diagnostic-item ${item.level}" type="button" ${item.nodeId ? `data-error-node="${escapeHtml(item.nodeId)}"` : ""}>
              <span>${escapeHtml(item.title)}</span>
              <strong>${escapeHtml(compactText(item.detail, 105))}</strong>
            </button>
          `
        )
        .join("")}
    </div>
  `;
}

function shouldRenderConnection(connection) {
  if (!connection || typeof connection !== "object") return false;
  if (connection.id === "e-reference-input-analyze" || connection.id === "e-reference-analyze-script") {
    return referenceFlowEnabled();
  }
  if (connection.id === "e-output-xhs") {
    return xhsPublishEnabled();
  }
  return true;
}

function statusLabel(status) {
  return {
    idle: "等待",
    draft: "待配置",
    queued: "排队中",
    processing: "制作中",
    running: "制作中",
    cancelled: "已取消",
    canceled: "已取消",
    done: "完成",
    completed: "完成",
    failed: "失败",
  }[status] || "等待";
}

function statusClass(status) {
  if (status === "done" || status === "completed") return "done";
  if (status === "running" || status === "processing") return "running";
  if (status === "queued") return "queued";
  if (status === "cancelled" || status === "canceled") return "waiting";
  return "waiting";
}

function getNodeHighlights(node) {
  const fields = node.fields;
  const type = node.type;
  if (type === "reference_input") {
    return [
      ["开关", fields.enabled || "关闭"],
      ["来源", fields.sourceType || "上传文件"],
      ["类型", fields.mediaType || "unknown"],
    ];
  }
  if (type === "reference_analyze") {
    return [
      ["配置", fields.model || "文本配置"],
      ["凭证", "server/.env"],
      ["目标", fields.focus || "风格分析"],
    ];
  }
  if (type === "input") {
    return [
      ["主角", fields.horse],
      ["时长", `${fields.duration}s / ${fields.aspect}`],
      ["场景", fields.audience],
    ];
  }
  if (type === "script") {
    return [
      ["配置", fields.model],
      ["风格", fields.style],
      ["格式", fields.jsonMode],
    ];
  }
  if (type === "storyboard") {
    return [
      ["分镜", `${fields.shotCount} 镜`],
      ["节奏", `${fields.shotSeconds}s / 镜`],
      ["镜头", fields.camera],
    ];
  }
  if (type === "keyframe") {
    const output = node.output || {};
    const requested = output.requestedFrameCount || fields.frameCount;
    const generated = output.generatedFrameCount || fields.frameCount;
    const reused = Number(output.reusedFrameCount || 0);
    const cacheHits = Number(output.cacheHits || 0);
    const quantityText = reused || cacheHits
      ? `生成 ${generated} / 复用 ${reused} / 缓存 ${cacheHits}`
      : `${requested} 张`;
    return [
      ["配置", fields.provider],
      ["尺寸", fields.apiSize || fields.imageSize],
      ["数量", quantityText],
      ["方式", output.referenceMode || fields.referenceMode],
    ];
  }
  if (type === "veo") {
    return [
      ["配置", fields.model || fields.provider],
      ["声音", fields.generateAudio === "是" ? "原生声音" : "关闭"],
      ["画幅", fields.aspect],
      ["并发", `${fields.parallel} 段`],
    ];
  }
  if (type === "voice") {
    return [
      ["方式", fields.mode],
      ["引擎", fields.engine],
      ["情绪", fields.emotion],
    ];
  }
  if (type === "subtitle") {
    return [
      ["方式", fields.mode],
      ["样式", fields.style],
      ["语言", fields.language],
    ];
  }
  if (type === "compose") {
    return [
      ["转场", fields.transition],
      ["音乐", fields.bgm],
      ["混音", fields.ducking],
    ];
  }
  if (type === "xhs_publish") {
    return [
      ["开关", fields.enabled || "关闭"],
      ["可见", fields.visibility || "公开可见"],
      ["Cookie", fields.cookiePath ? "已填写" : "未填写"],
    ];
  }
  return [
    ["保存", fields.saveTo],
    ["回传", fields.callback],
    ["动作", fields.publish],
  ];
}

function normalizeNodeStatus(status) {
  const value = String(status || "idle").toLowerCase();
  if (value === "completed") return "done";
  if (value === "processing") return "running";
  return value;
}

function buildWorkflowInputPayload() {
  const referenceNode = findNode("reference_input");
  const referenceAnalyzeNode = findNode("reference_analyze");
  const xhsNode = findNode("xhs_publish");
  const referenceEnabled = referenceFlowEnabled();
  const xhsEnabled = xhsPublishEnabled();
  return {
    horse: findNode("input")?.fields.horse || "",
    horse_name: findNode("input")?.fields.horse || "",
    topic: findNode("input")?.fields.topic || "",
    brief: findNode("input")?.fields.brief || "",
    audience: findNode("input")?.fields.audience || "",
    duration: Number(findNode("input")?.fields.duration || 30),
    aspect_ratio: findNode("input")?.fields.aspect || "9:16",
    run_mode: findNode("input")?.fields.runMode || "成片模式",
    video_count: parsePositiveInt(findNode("input")?.fields.videoCount || "1", 1),
    baseTemplate: BASE_VIDEO_TEMPLATE.id,
    baseTemplateName: BASE_VIDEO_TEMPLATE.name,
    baseTemplateSource: BASE_VIDEO_TEMPLATE.source,
    script: { ...findNode("script")?.fields },
    storyboard: { ...findNode("storyboard")?.fields },
    keyframe: { ...findNode("keyframe")?.fields },
    veo: { ...findNode("veo")?.fields },
    voice: { ...findNode("voice")?.fields },
    subtitle: { ...findNode("subtitle")?.fields },
    compose: { ...findNode("compose")?.fields },
    output: { ...findNode("output")?.fields },
    enableReferenceFlow: referenceEnabled,
    enableXhsPublish: xhsEnabled,
    reference: {
      enabled: referenceEnabled,
      sourceType: referenceNode?.fields?.sourceType || "上传文件",
      mediaType: referenceNode?.fields?.mediaType || "unknown",
      mediaUrl: referenceNode?.fields?.mediaUrl || "",
      localPath: referenceNode?.fields?.localPath || "",
      assets: referenceAssetsFromFields(referenceNode?.fields || {}),
      weights: referenceWeightsFromFields(referenceNode?.fields || {}).normalized,
      model: referenceAnalyzeNode?.fields?.model || "",
      focus: referenceAnalyzeNode?.fields?.focus || "",
      note: referenceNode?.fields?.note || "",
    },
    xhs: {
      enabled: xhsEnabled,
      cookiePath: xhsNode?.fields?.cookiePath || "",
      title: xhsNode?.fields?.title || "",
      content: xhsNode?.fields?.content || "",
      tags: xhsNode?.fields?.tags || "",
      visibility: xhsNode?.fields?.visibility || "",
      publishMode: xhsNode?.fields?.publishMode || "direct",
      scheduledAt: xhsNode?.fields?.scheduledAt || "",
      rollbackOnFail: xhsNode?.fields?.rollbackOnFail || "warn",
      autoCommentEnabled: xhsNode?.fields?.autoCommentEnabled || "关闭",
      autoCommentText: xhsNode?.fields?.autoCommentText || "",
      autoCommentDelaySeconds: xhsNode?.fields?.autoCommentDelaySeconds || "0",
      autoCommentPath: xhsNode?.fields?.autoCommentPath || "",
      collectCommentsEnabled: xhsNode?.fields?.collectCommentsEnabled || "关闭",
      collectCommentsLimit: xhsNode?.fields?.collectCommentsLimit || "20",
      collectCommentsIncludeReplies: xhsNode?.fields?.collectCommentsIncludeReplies || "关闭",
      collectCommentsPath: xhsNode?.fields?.collectCommentsPath || "",
      baseUrl: xhsNode?.fields?.baseUrl || "",
      publishPath: xhsNode?.fields?.publishPath || "",
      note: xhsNode?.fields?.note || "",
    },
  };
}

function syncConnectionStates() {
  workflow.connections.forEach((connection) => {
    if (!shouldRenderConnection(connection)) {
      connection.status = "idle";
      return;
    }
    const fromNode = findNode(connection.from);
    const toNode = findNode(connection.to);
    if (!fromNode || !toNode) {
      connection.status = "idle";
      return;
    }

    const fromDone = ["done", "completed"].includes(fromNode.status);
    const toDone = ["done", "completed"].includes(toNode.status);
    const toActive = ["queued", "running", "processing"].includes(toNode.status);

    if (fromDone && toDone) {
      connection.status = "done";
    } else if (fromDone && toActive) {
      connection.status = "flowing";
    } else {
      connection.status = "idle";
    }
  });
}

function activeRuntimeState() {
  return activeTask?.runtime_state && typeof activeTask.runtime_state === "object"
    ? activeTask.runtime_state
    : null;
}

function activeRuntimeEvents() {
  const runtime = activeRuntimeState();
  return Array.isArray(runtime?.events) ? runtime.events : [];
}

function runtimeNodeStateMap() {
  const runtime = activeRuntimeState();
  const nodeStates = Array.isArray(runtime?.nodeStates) && runtime.nodeStates.length
    ? runtime.nodeStates
    : activeTask?.node_states || [];
  return new Map(nodeStates.map((state) => [state.node_id, state]));
}

function currentExecutionNodeId() {
  return activeRuntimeState()?.currentNode || activeTask?.current_node || "";
}

function activeExecutionNodeIds() {
  const runtime = activeRuntimeState();
  const activeNodes = Array.isArray(runtime?.activeNodes) ? runtime.activeNodes : [];
  const ids = activeNodes
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  const current = currentExecutionNodeId();
  if (current) {
    ids.push(...String(current).split(",").map((value) => value.trim()).filter(Boolean));
  }
  return new Set(ids);
}

function nodeVisualPhase(node) {
  const status = normalizeNodeStatus(node.status);
  if (activeExecutionNodeIds().has(node.id) && ["queued", "running"].includes(status)) {
    return "current";
  }
  if (status === "done") return "done";
  if (status === "failed") return "failed";
  if (status === "queued") return "queued";
  if (status === "running") return "running";
  return "idle";
}

function connectionVisualPhase(connection) {
  const fromNode = findNode(connection.from);
  const toNode = findNode(connection.to);
  if (!fromNode || !toNode) return "idle";
  const fromStatus = normalizeNodeStatus(fromNode.status);
  const toStatus = normalizeNodeStatus(toNode.status);
  const activeNodeIds = activeExecutionNodeIds();
  if (toStatus === "failed" || fromStatus === "failed") return "failed";
  if (fromStatus === "done" && toStatus === "done") return "done";
  if (connection.status === "flowing" || activeNodeIds.has(toNode.id) || (fromStatus === "done" && ["queued", "running"].includes(toStatus))) {
    return "flowing";
  }
  if (fromStatus === "done") return "primed";
  return "idle";
}

function applyTaskSnapshot(task) {
  if (!task) return;

  activeTask = task;
  activeTaskId = task.task_id || activeTaskId;
  const runtime = activeRuntimeState();
  isRunning = ["queued", "processing"].includes(runtime?.status || task.status);

  const inputNode = findNode("input");
  if (inputNode && task.input_payload) {
    inputNode.fields.horse = task.input_payload.horse_name || task.input_payload.horse || inputNode.fields.horse;
    inputNode.fields.topic = task.input_payload.topic || task.title || inputNode.fields.topic;
    inputNode.fields.brief = task.input_payload.brief || inputNode.fields.brief;
    inputNode.fields.audience = task.input_payload.audience || inputNode.fields.audience;
    inputNode.fields.duration = String(task.duration || inputNode.fields.duration);
    inputNode.fields.aspect = task.aspect_ratio || task.input_payload.aspect_ratio || inputNode.fields.aspect;
  }

  const byId = runtimeNodeStateMap();
  workflow.nodes.forEach((node) => {
    const state = byId.get(node.id);
    if (!state) return;
    node.runtimeState = state;
    node.status = normalizeNodeStatus(state.status);
    node.progress = Number(state.progress || 0);
    node.output = state.output && Object.keys(state.output).length ? state.output : node.output;
  });

  syncConnectionStates();

  const taskStatus = statusLabel(task.status);
  els.workflowStatus.textContent = taskStatus;
  els.payloadSummary.textContent =
    task.result_payload?.videoUrl ||
    task.result_payload?.note ||
    `${task.title} / ${task.duration}s / ${task.aspect_ratio}`;
  els.runTitle.textContent = `${task.title} · ${taskStatus}`;

  const outputNode = findNode("output");
  if (outputNode) {
    const resultPayload = task.result_payload || {};
    if (Object.keys(resultPayload).length) {
      outputNode.output = resultPayload;
      outputNode.status = normalizeNodeStatus(task.status);
      outputNode.progress = Number(task.progress || outputNode.progress || 0);
    }
  }

  if (task.status === "completed") {
    const index = parsePositiveInt(task?.input_payload?.batch?.index, generatedVideos.length + 1);
    const total = parsePositiveInt(task?.input_payload?.batch?.total, batchRunState?.total || targetVideoCount());
    upsertGeneratedVideoTask(task, index, total);
    rememberNodeHistory(task, index);
    attachGeneratedVideosToOutputNode();
    if (!selectedGeneratedTaskId) {
      selectedGeneratedTaskId = task.task_id || "";
    }
  }

  render();
}

function isRealVideoUrl(value) {
  const text = String(value || "").trim();
  return Boolean(text) && !text.startsWith("pending://") && !text.startsWith("mock://");
}

function firstRealVideoUrlFromOutput(output) {
  if (!output || typeof output !== "object") return "";
  if (isRealVideoUrl(output.videoUrl)) return output.videoUrl;
  if (isRealVideoUrl(output.firstVideoUrl)) return output.firstVideoUrl;
  const sourceClips = Array.isArray(output.sourceClips) ? output.sourceClips : [];
  const directClip = sourceClips.find((url) => isRealVideoUrl(url));
  if (directClip) return directClip;
  const clips = Array.isArray(output.clips) ? output.clips : [];
  for (const clip of clips) {
    if (isRealVideoUrl(clip?.url)) return clip.url;
    if (isRealVideoUrl(clip?.videoUrl)) return clip.videoUrl;
  }
  return "";
}

function getTaskVideoUrl(task) {
  const directUrl = firstRealVideoUrlFromOutput(task?.result_payload);
  if (directUrl) return directUrl;
  for (const state of task?.node_states || []) {
    const output = state?.output || {};
    const url = firstRealVideoUrlFromOutput(output);
    if (url) return url;
  }
  return "";
}

function parsePositiveInt(value, fallback = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  const intValue = Math.max(1, Math.floor(number));
  return intValue || fallback;
}

function targetVideoCount() {
  const raw = findNode("input")?.fields?.videoCount || "1";
  const count = parsePositiveInt(raw, 1);
  if ([1, 3, 5, 10].includes(count)) return count;
  return 1;
}

function currentRunMode() {
  return String(findNode("input")?.fields?.runMode || "成片模式").trim() || "成片模式";
}

function applyRunModePreset(mode, { silent = false } = {}) {
  const input = findNode("input");
  const storyboard = findNode("storyboard");
  const keyframe = findNode("keyframe");
  const veo = findNode("veo");
  const compose = findNode("compose");
  if (!input || !storyboard || !keyframe || !veo || !compose) return;

  const normalizedMode = String(mode || "成片模式").includes("快速") ? "快速预览" : "成片模式";
  input.fields.runMode = normalizedMode;

  if (normalizedMode === "快速预览") {
    input.fields.duration = "15";
    storyboard.fields.shotCount = "1";
    storyboard.fields.shotSeconds = "4";
    keyframe.fields.frameCount = "2";
    keyframe.fields.referenceMode = "首尾关键帧";
    veo.fields.parallel = "1";
    veo.fields.quality = "standard";
    compose.fields.bgm = "不添加";
    if (!silent) {
      addLog("制作模式", "已切换为快速预览：单分镜、单片段、低成本试方向。");
    }
  } else {
    if (String(storyboard.fields.shotCount || "1") === "1") storyboard.fields.shotCount = "3";
    if (String(storyboard.fields.shotSeconds || "4") === "4") storyboard.fields.shotSeconds = "8";
    if (String(keyframe.fields.frameCount || "1") === "1") keyframe.fields.frameCount = "2";
    keyframe.fields.referenceMode = "首尾关键帧";
    if (String(veo.fields.parallel || "1") === "1") veo.fields.parallel = "3";
    veo.fields.quality = "high";
    if (String(compose.fields.bgm || "") === "不添加") compose.fields.bgm = "史诗鼓点";
    if (!silent) {
      addLog("制作模式", "已切换为成片模式：多分镜、多片段、首尾关键帧衔接。");
    }
  }
}

function setNodeFields(nodeId, patch = {}) {
  const node = findNode(nodeId);
  if (!node || !patch || typeof patch !== "object") return false;
  node.fields = { ...(node.fields || {}), ...patch };
  if (node.status !== "idle") {
    node.status = "idle";
    node.progress = 0;
    node.output = null;
  }
  return true;
}

function applyParameterPreset(presetId) {
  const preset = PARAMETER_PRESETS.find((item) => item.id === presetId);
  if (!preset) return;
  const inputPatch = preset.patches?.input || {};
  if (inputPatch.runMode) {
    applyRunModePreset(inputPatch.runMode, { silent: true });
  }
  Object.entries(preset.patches || {}).forEach(([nodeId, patch]) => {
    setNodeFields(nodeId, patch);
  });
  selectedPresetId = preset.id;
  saveWorkflow();
  addLog("参数预设", `已应用「${preset.name}」，节点参数已同步。`);
  render();
}

function presetPatchSummary(preset) {
  const patches = preset?.patches || {};
  const input = patches.input || {};
  const storyboard = patches.storyboard || {};
  const keyframe = patches.keyframe || {};
  const veo = patches.veo || {};
  return [
    storyboard.shotCount ? `${storyboard.shotCount} 分镜` : "",
    storyboard.shotSeconds ? `${storyboard.shotSeconds}s/镜` : "",
    keyframe.frameCount ? `${keyframe.frameCount} 首尾帧` : "",
    veo.parallel ? `Veo ${veo.parallel} 路` : "",
    input.videoCount ? `${input.videoCount} 条` : "",
  ].filter(Boolean).join(" · ") || "按节点参数更新";
}

function presetPatchTags(preset) {
  const labels = {
    input: "输入",
    script: "剧本",
    storyboard: "分镜",
    keyframe: "关键帧",
    voice: "声音",
    subtitle: "字幕",
    veo: "Veo",
    compose: "合成",
    output: "输出",
    xhs_publish: "小红书",
  };
  return Object.keys(preset?.patches || {})
    .map((key) => labels[key] || key)
    .slice(0, 6);
}

function renderPresetPanel() {
  if (!els.presetPanel) return;
  const currentPreset = PARAMETER_PRESETS.find((preset) => preset.id === selectedPresetId) || PARAMETER_PRESETS[0];
  els.presetPanel.innerHTML = `
    <label class="preset-picker-label" for="presetSelect">一键参数预设</label>
    <div class="preset-picker-row">
      <select id="presetSelect" class="preset-select">
        ${PARAMETER_PRESETS.map((preset) => `
          <option value="${escapeHtml(preset.id)}" ${currentPreset?.id === preset.id ? "selected" : ""}>
            ${escapeHtml(preset.name)}
          </option>
        `).join("")}
      </select>
      <button type="button" class="preset-apply-button" data-apply-selected-preset>应用</button>
    </div>
    <div class="preset-selected-card ${currentPreset ? `accent-${currentPreset.accent}` : ""}">
      <div class="preset-card-head">
        <strong>${escapeHtml(currentPreset?.name || "选择模板")}</strong>
        <em>${escapeHtml(currentPreset ? presetPatchSummary(currentPreset) : "选择后应用")}</em>
      </div>
      <span>${escapeHtml(currentPreset?.desc || "从上方选择一个模板，再点击应用。")}</span>
      <div class="preset-card-tags">
        ${(currentPreset ? presetPatchTags(currentPreset) : []).map((tag) => `<i>${escapeHtml(tag)}</i>`).join("")}
      </div>
    </div>
  `;
}

function resetGeneratedVideoState() {
  generatedVideos = [];
  selectedGeneratedTaskId = "";
  nodeOutputHistory = {};
}

function summarizeNodeHistory(nodeId, output) {
  const data = output && typeof output === "object" ? output : {};
  if (nodeId === "script") {
    return compactText(data.title || data.voiceover || data.note || "script generated", 72);
  }
  if (nodeId === "storyboard") {
    const shotCount = Array.isArray(data.shots) ? data.shots.length : 0;
    const seconds = data.shotSeconds || data.totalSeconds || "";
    return compactText(
      shotCount ? `${shotCount} shots${seconds ? ` / ${seconds}s` : ""}` : data.note || "storyboard generated",
      72
    );
  }
  if (nodeId === "keyframe") {
    const count = Array.isArray(data.images) ? data.images.length : 0;
    return compactText(count ? `${count} keyframes ready` : "keyframes generated", 72);
  }
  if (nodeId === "veo") {
    const count = Array.isArray(data.clips) ? data.clips.length : 0;
    return compactText(count ? `${count} clips generated` : data.summary || "veo generated", 72);
  }
  if (nodeId === "voice") {
    return compactText(data.voiceover || data.note || "voice planned", 72);
  }
  if (nodeId === "subtitle") {
    const count = Array.isArray(data.segments) ? data.segments.length : 0;
    return compactText(count ? `${count} subtitle lines` : data.note || "subtitle planned", 72);
  }
  if (nodeId === "compose") {
    return compactText(data.videoUrl ? "composition completed" : data.note || "composed", 72);
  }
  if (nodeId === "output") {
    return compactText(data.videoUrl || data.note || "output completed", 72);
  }
  return compactText(JSON.stringify(data), 72);
}

function rememberNodeHistory(task, batchIndex) {
  const states = Array.isArray(task?.node_states) ? task.node_states : [];
  states.forEach((state) => {
    const nodeId = String(state?.node_id || "").trim();
    if (!nodeId) return;
    const output = state?.output;
    if (!output || typeof output !== "object" || !Object.keys(output).length) return;
    if (!nodeOutputHistory[nodeId]) {
      nodeOutputHistory[nodeId] = [];
    }
    if (nodeOutputHistory[nodeId].some((item) => item.taskId === (task.task_id || "") && item.batchIndex === batchIndex)) {
      return;
    }
    nodeOutputHistory[nodeId].push({
      batchIndex,
      taskId: task.task_id || "",
      summary: summarizeNodeHistory(nodeId, output),
    });
    nodeOutputHistory[nodeId] = nodeOutputHistory[nodeId].slice(-10);
  });
}

function upsertGeneratedVideoTask(task, batchIndex = 1, batchTotal = 1) {
  if (!task?.task_id) return;
  const videoUrl = getTaskVideoUrl(task);
  if (!videoUrl) return;
  const resultPayload = task.result_payload && typeof task.result_payload === "object" ? task.result_payload : {};
  const index = generatedVideos.findIndex((item) => item.taskId === task.task_id);
  const entry = {
    taskId: task.task_id,
    title: task.title || `Video ${batchIndex}`,
    videoUrl,
    coverUrl: safeMediaUrl(resultPayload.coverUrl || resultPayload.thumbnailUrl || resultPayload.posterUrl),
    duration: Number(task.duration || 0),
    aspect: task.aspect_ratio || "9:16",
    status: task.status || "completed",
    horse: task.horse_name || task.input_payload?.horse_name || task.input_payload?.horse || "",
    runMode: task.input_payload?.run_mode || task.input_payload?.runMode || "",
    batchIndex,
    batchTotal,
    createdAt: task.updated_at || task.created_at || "",
  };
  if (index === -1) {
    generatedVideos.push(entry);
  } else {
    generatedVideos[index] = { ...generatedVideos[index], ...entry };
  }
  generatedVideos.sort((a, b) => {
    if (a.batchIndex !== b.batchIndex) return a.batchIndex - b.batchIndex;
    return a.taskId.localeCompare(b.taskId);
  });
  if (!selectedGeneratedTaskId) {
    selectedGeneratedTaskId = entry.taskId;
  }
}

function generatedTaskById(taskId) {
  if (!taskId) return null;
  return tasks.find((item) => item.task_id === taskId) || (activeTask?.task_id === taskId ? activeTask : null);
}

function previewTaskFromState() {
  const selectedTask = generatedTaskById(selectedGeneratedTaskId);
  if (selectedTask && getTaskVideoUrl(selectedTask)) return selectedTask;
  if (activeTask && getTaskVideoUrl(activeTask)) return activeTask;
  const latestGenerated = generatedVideos.find((item) => item.videoUrl);
  if (latestGenerated) {
    return generatedTaskById(latestGenerated.taskId);
  }
  return null;
}

function renderGeneratedVideoMenu() {
  if (!els.generatedVideoMenu) return;
  if (!generatedVideos.length) {
    els.generatedVideoMenu.innerHTML = `
      <div class="video-menu-empty">
        <strong>成片库等待更新</strong>
        <span>运行完成后，每条视频会自动进入这里，可预览、下载和继续发布。</span>
      </div>
    `;
    return;
  }
  const total = batchRunState?.total || targetVideoCount();
  els.generatedVideoMenu.innerHTML = `
    <div class="video-library-head">
      <div>
        <strong>成片库</strong>
        <span>${generatedVideos.length}/${total} 条可管理作品</span>
      </div>
      <button class="video-library-mini" type="button" data-refresh-generated-library>刷新</button>
    </div>
    ${generatedVideos
      .map((item, index) => {
      const active = item.taskId === selectedGeneratedTaskId;
      const completed = item.status === "completed";
      const summary = [item.duration ? `${item.duration}s` : "", item.aspect].filter(Boolean).join(" / ");
      const created = item.createdAt ? String(item.createdAt).replace("T", " ").slice(0, 16) : "";
      const cover = safeMediaUrl(item.coverUrl);
      return `
        <div class="video-menu-item ${active ? "active" : ""}">
          <button class="video-menu-select" type="button" data-select-generated-task="${item.taskId}">
            <span class="video-menu-thumb">
              ${
                cover
                  ? `<img src="${escapeHtml(cover)}" alt="${escapeHtml(item.title)}" loading="lazy" />`
                  : `<span>${String(index + 1).padStart(2, "0")}</span>`
              }
            </span>
            <span class="video-menu-copy">
              <strong>${escapeHtml(item.title)}</strong>
              <small>${escapeHtml([item.horse, item.runMode, summary].filter(Boolean).join(" · "))}</small>
              ${created ? `<em>${escapeHtml(created)}</em>` : ""}
            </span>
          </button>
          <div class="video-menu-actions">
            <button class="video-menu-download" type="button" data-download-task-id="${item.taskId}" ${completed ? "" : "disabled"}>下载</button>
            <a class="video-menu-open" href="${escapeHtml(item.videoUrl)}" target="_blank" rel="noopener">打开</a>
            <button class="video-menu-reuse" type="button" data-reuse-generated-task="${item.taskId}">复用</button>
            <button class="video-menu-delete" type="button" data-delete-generated-task="${item.taskId}">删除</button>
          </div>
        </div>
      `;
    })
    .join("")}
  `;
}

function taskDownloadUrl(taskId) {
  return `${WORKFLOW_API_BASE}/tasks/${encodeURIComponent(taskId)}/download`;
}

function safeMediaUrl(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (text.startsWith("/generated/")) return text;
  if (
    text.startsWith("../images/") ||
    text.startsWith("./images/") ||
    text.startsWith("images/") ||
    text.startsWith("/images/")
  ) return text;
  if (/^https?:\/\//i.test(text)) return text;
  return "";
}

function safeDownloadFilename(value, fallback = "video.mp4") {
  const text = String(value || "").trim();
  if (!text) return fallback;
  const cleaned = text.replace(/[<>:"/\\|?*\x00-\x1F]/g, "_");
  return cleaned || fallback;
}

function taskDownloadFilename(task) {
  const title = String(task?.title || "").trim().replace(/\s+/g, "_");
  const base = safeDownloadFilename(title, "video");
  const suffix = String(task?.task_id || "").trim();
  const name = suffix ? `${base}_${suffix}` : base;
  return name.toLowerCase().endsWith(".mp4") ? name : `${name}.mp4`;
}

function filenameFromDisposition(disposition, fallback) {
  const value = String(disposition || "");
  if (!value) return fallback;

  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return safeDownloadFilename(decodeURIComponent(utf8Match[1]), fallback);
    } catch {
      // ignore and continue
    }
  }

  const plainMatch = value.match(/filename="?([^\";]+)"?/i);
  if (plainMatch?.[1]) {
    return safeDownloadFilename(plainMatch[1], fallback);
  }
  return fallback;
}

function triggerBrowserDownloadUrl(url, filename = "") {
  const href = safeMediaUrl(url);
  if (!href) return false;
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  link.rel = "noopener";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  return true;
}

function triggerBlobDownload(blob, filename) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = safeDownloadFilename(filename || "video.mp4", "video.mp4");
  link.rel = "noopener";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 4000);
}

async function triggerTaskDownload(task) {
  if (!task?.task_id || !getTaskVideoUrl(task)) return false;
  const fallbackFilename = taskDownloadFilename(task);
  const directUrl = safeMediaUrl(getTaskVideoUrl(task));
  const headers = new Headers();
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    const response = await fetch(taskDownloadUrl(task.task_id), {
      method: "GET",
      headers,
      credentials: "include",
    });
    if (response.ok) {
      const contentType = String(response.headers.get("content-type") || "").toLowerCase();
      const isVideoPayload =
        contentType.includes("video/") || contentType.includes("application/octet-stream");
      if (isVideoPayload) {
        const blob = await response.blob();
        if (blob.size > 0) {
          const filename = filenameFromDisposition(
            response.headers.get("content-disposition"),
            fallbackFilename
          );
          triggerBlobDownload(blob, filename);
          return true;
        }
      }
    }
  } catch {
    // fall through to direct media URL
  }

  if (directUrl) {
    return triggerBrowserDownloadUrl(directUrl, fallbackFilename);
  }
  return false;
}

function downloadButtonTask() {
  const selectedTask = generatedTaskById(selectedGeneratedTaskId);
  if (selectedTask && getTaskVideoUrl(selectedTask)) return selectedTask;
  if (activeTask && getTaskVideoUrl(activeTask)) return activeTask;
  return tasks.find((task) => task.task_id === activeTaskId && getTaskVideoUrl(task)) || null;
}

function renderDownloadButton() {
  if (!els.downloadVideoBtn) return;
  const task = downloadButtonTask();
  const hasDownloadedCurrent = Boolean(task?.task_id && downloadedTaskId === task.task_id);
  const canDownload = Boolean(
    task?.task_id && task.status === "completed" && getTaskVideoUrl(task) && !hasDownloadedCurrent
  );
  els.downloadVideoBtn.disabled = !canDownload;
  els.downloadVideoBtn.classList.toggle("ready", canDownload);
  if (canDownload) {
    els.downloadVideoBtn.textContent = "下载成片";
    els.downloadVideoBtn.title = "点击下载当前制作完成的视频";
  } else if (hasDownloadedCurrent) {
    els.downloadVideoBtn.textContent = "制作完成后可下载";
    els.downloadVideoBtn.title = "当前视频已提交下载，重新运行后可再次下载新成片";
  } else if (isRunning || ["queued", "processing"].includes(activeTask?.status || "")) {
    els.downloadVideoBtn.textContent = "制作中";
    els.downloadVideoBtn.title = "制作完成后才能下载";
  } else {
    els.downloadVideoBtn.textContent = "制作完成后可下载";
    els.downloadVideoBtn.title = "当前还没有可下载的视频";
  }
}

async function downloadCurrentTaskVideo() {
  const task = downloadButtonTask();
  if (!task || task.status !== "completed" || !getTaskVideoUrl(task)) {
    addLog("下载提示", "制作还没完成，或暂未返回可下载的视频地址。");
    renderDownloadButton();
    return;
  }
  const ok = await triggerTaskDownload(task);
  if (!ok) {
    addLog("下载失败", "当前任务没有可下载的视频文件，请刷新任务后重试。");
    return;
  }
  downloadedTaskId = task.task_id;
  addLog("下载成片", "已提交到浏览器下载栏。");
  renderDownloadButton();
  return;
  if (false) {
    downloadedTaskId = task.task_id;
    addLog("下载成片", "已提交到浏览器下载栏。");
    renderDownloadButton();
  }
}

async function downloadTaskVideoById(taskId) {
  if (!taskId) return;
  const task = generatedTaskById(taskId);
  if (!task || task.status !== "completed" || !getTaskVideoUrl(task)) {
    addLog("下载提示", "该任务暂时没有可下载的视频。");
    return;
  }
  const ok = await triggerTaskDownload(task);
  if (!ok) {
    addLog("下载失败", "该任务的视频下载失败，请稍后重试。");
    return;
  }
  downloadedTaskId = task.task_id;
  selectedGeneratedTaskId = task.task_id;
  if (activeTaskId === task.task_id) {
    renderDownloadButton();
  }
  renderGeneratedVideoMenu();
  renderPreview();
}

function taskSignature(task) {
  return JSON.stringify([
    task?.status,
    task?.progress,
    task?.current_node,
    task?.error_message,
    (task?.node_states || []).map((node) => [node.node_id, node.status, node.progress]),
  ]);
}

function logTaskUpdate(task, force = false) {
  const signature = taskSignature(task);
  if (!force && signature === lastTaskSignature) {
    return;
  }
  lastTaskSignature = signature;
  const currentNode = task.current_node ? ` / ${task.current_node}` : "";
  addLog("任务状态", `${statusLabel(task.status)} ${task.progress || 0}%${currentNode}`);
    if (task.error_message) {
      addLog("任务错误", task.error_message);
    }
  }

function clearTaskPolling() {
  if (taskPollTimer) {
    window.clearInterval(taskPollTimer);
    taskPollTimer = null;
  }
}

function startTaskPolling(taskId) {
  clearTaskPolling();
  if (!taskId) return;
  taskPollTimer = window.setInterval(async () => {
    try {
      const task = await apiRequest(`/tasks/${taskId}`);
      rememberTask(task);
      applyTaskSnapshot(task);
      logTaskUpdate(task);
      renderTaskList();
      if (!["draft", "queued", "processing"].includes(task.status)) {
        clearTaskPolling();
      }
    } catch (error) {
      addLog("轮询失败", error.message || "无法更新任务状态。");
      clearTaskPolling();
      isRunning = false;
      render();
    }
  }, TASK_POLL_MS);
}

async function hydrateLatestTask() {
  if (!getAccessToken()) return;
  try {
    const result = await apiRequest("/tasks?limit=1");
    const task = result?.items?.[0];
    if (!task) return;
    rememberTask(task);
    applyTaskSnapshot(task);
    logTaskUpdate(task, true);
    if (["draft", "queued", "processing"].includes(task.status)) {
      startTaskPolling(task.task_id);
    }
  } catch {
    // Ignore hydration failures quietly to avoid blocking the page.
  }
}

function rememberTask(task) {
  if (!task?.task_id) return;
  const existingIndex = tasks.findIndex((item) => item.task_id === task.task_id);
  if (existingIndex === -1) {
    tasks = [task, ...tasks].slice(0, 12);
  } else {
    tasks[existingIndex] = task;
    tasks = [tasks[existingIndex], ...tasks.filter((_, index) => index !== existingIndex)];
  }
}

function renderTaskList() {
  if (!els.taskList) return;
  if (!getAccessToken()) {
    els.taskList.innerHTML = `<div class="task-list-empty">登录后会显示最近的制作任务。</div>`;
    return;
  }
  if (!tasks.length) {
    els.taskList.innerHTML = `<div class="task-list-empty">还没有制作任务。点击“开始制作”后，这里会显示最近的记录。</div>`;
    return;
  }

  els.taskList.innerHTML = tasks
    .map((task) => {
      const active = task.task_id === activeTaskId;
      const meta = `${task.horse_name || "未指定名马"} / ${task.duration}s / ${task.aspect_ratio}`;
      const hasVideo = Boolean(getTaskVideoUrl(task));
      return `
        <div class="task-card ${active ? "active" : ""}">
          <button class="task-delete-button" type="button" data-delete-task-id="${task.task_id}" title="删除这条历史">删除</button>
          <button class="task-card-main" data-task-id="${task.task_id}">
          <div class="task-card-title">${escapeHtml(task.title)}</div>
          <div class="task-card-meta">${escapeHtml(meta)}</div>
          <div class="task-card-row">
            <span class="status-pill ${statusClass(task.status)}">${statusLabel(task.status)}</span>
            <span class="task-card-meta">${task.progress || 0}%</span>
          </div>
          <div class="task-card-progress"><span style="width:${task.progress || 0}%"></span></div>
          </button>
          ${
            hasVideo
              ? `<button class="task-download-link" type="button" data-download-task-id="${task.task_id}">下载成片</button>`
              : ""
          }
        </div>
      `;
    })
    .join("");
}

async function refreshTaskList() {
  if (!getAccessToken()) {
    renderTaskList();
    return;
  }
  try {
    const result = await apiRequest("/tasks?limit=12");
    tasks = Array.isArray(result?.items) ? result.items : [];
    renderTaskList();
  } catch (error) {
    addLog("任务列表", error.message || "无法加载任务历史。");
  }
}

async function deleteTaskHistory(taskId) {
  if (!taskId || !getAccessToken()) return;
  const task = tasks.find((item) => item.task_id === taskId);
  const label = task?.title ? `“${task.title}”` : "这条任务历史";
  if (!window.confirm(`确定删除${label}吗？生成文件也会一起清理。`)) return;
  try {
    await apiRequest(`/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
    tasks = tasks.filter((item) => item.task_id !== taskId);
    if (activeTaskId === taskId) {
      activeTaskId = null;
      activeTask = null;
      downloadedTaskId = "";
      clearTaskPolling();
    }
    generatedVideos = generatedVideos.filter((item) => item.taskId !== taskId);
    if (selectedGeneratedTaskId === taskId) {
      selectedGeneratedTaskId = generatedVideos[0]?.taskId || "";
    }
    addLog("任务历史", "已删除 1 条历史记录。");
    render();
  } catch (error) {
    addLog("任务历史", error.message || "删除任务历史失败。");
  }
}

async function clearTaskHistory() {
  if (!getAccessToken()) {
    renderTaskList();
    return;
  }
  if (!tasks.length) {
    addLog("任务历史", "当前没有可清空的历史记录。");
    return;
  }
  if (!window.confirm("确定清空全部任务历史吗？所有本地生成文件也会一起清理。")) return;
  try {
    const result = await apiRequest("/tasks", { method: "DELETE" });
    const count = Number(result?.deleted_count || tasks.length || 0);
    tasks = [];
    activeTaskId = null;
    activeTask = null;
    downloadedTaskId = "";
    resetGeneratedVideoState();
    clearTaskPolling();
    addLog("任务历史", `已清空 ${count} 条历史记录。`);
    render();
  } catch (error) {
    addLog("任务历史", error.message || "清空任务历史失败。");
  }
}

async function selectTask(taskId) {
  if (!taskId) return;
  try {
    const task = await apiRequest(`/tasks/${taskId}`);
    rememberTask(task);
    applyTaskSnapshot(task);
    logTaskUpdate(task, true);
    renderTaskList();
    if (["draft", "queued", "processing"].includes(task.status)) {
      startTaskPolling(task.task_id);
    } else {
      clearTaskPolling();
    }
  } catch (error) {
    addLog("任务详情", error.message || "无法读取任务详情。");
  }
}

async function reuseGeneratedTaskConfig(taskId) {
  if (!taskId || !getAccessToken()) return;
  try {
    const task = generatedTaskById(taskId) || (await apiRequest(`/tasks/${encodeURIComponent(taskId)}`));
    rememberTask(task);
    applyTaskSnapshot(task);
    selectedGeneratedTaskId = task.task_id || taskId;
    addLog("成片库", "已把该作品配置带回画布，可调整后重新运行。");
    render();
  } catch (error) {
    addLog("成片库", error.message || "复用作品配置失败。");
  }
}

async function retryActiveTask() {
  if (!activeTaskId) {
    addLog("重新制作", "请先在左侧任务历史中选择一个任务。");
    return;
  }
  try {
    const result = await apiRequest(`/tasks/${activeTaskId}/run`, {
      method: "POST",
    });
    const task = result?.task;
    if (!task) {
      throw new Error("站内服务没有返回任务状态。");
    }
    rememberTask(task);
    applyTaskSnapshot(task);
    logTaskUpdate(task, true);
    renderTaskList();
    if (["queued", "processing"].includes(task.status)) {
      startTaskPolling(task.task_id);
    }
  } catch (error) {
    addLog("重新制作", error.message || "无法重新制作当前任务。");
  }
}

function render() {
  if (autoFitZoom) {
    zoom = getFitZoom();
    centerCanvas();
  }
  renderAuthLink();
  renderPresetPanel();
  renderTaskList();
  renderNodeList();
  renderNodes();
  renderLinks();
  renderInspector();
  renderPreview();
  renderStats();
  renderExecutionTimeline();
  renderExecutionPulse();
  renderBatchQueue();
  renderRuntimeEvents();
  renderNodeBriefGrid();
  renderPreflightPanel();
  renderErrorCenter();
  renderDownloadButton();
  applyCanvasZoom();
  els.zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
}

function getFitZoom() {
  const box = els.canvasViewport.getBoundingClientRect();
  if (!box.width || !box.height) {
    return 1;
  }
  const widthZoom = (box.width - 24) / CANVAS_WIDTH;
  const heightZoom = (box.height - 24) / CANVAS_HEIGHT;
  return Math.max(0.45, Math.min(1, widthZoom, heightZoom));
}

function centerCanvas() {
  const box = els.canvasViewport.getBoundingClientRect();
  if (!box.width || !box.height) return;
  const scaledWidth = CANVAS_WIDTH * zoom;
  const scaledHeight = CANVAS_HEIGHT * zoom;
  panX = (box.width - scaledWidth) / 2;
  panY = (box.height - scaledHeight) / 2;
}

function applyCanvasZoom() {
  els.canvasInner.style.zoom = "";
  els.canvasInner.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
}

function setCanvasView(nextPanX, nextPanY, nextZoom) {
  panX = nextPanX;
  panY = nextPanY;
  zoom = Math.max(0.7, Math.min(1.25, Number(nextZoom) || zoom));
  applyCanvasZoom();
  if (els.zoomLabel) {
    els.zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
  }
}

function animateCanvasView(targetPanX, targetPanY, targetZoom) {
  if (canvasFocusFrame) {
    window.cancelAnimationFrame(canvasFocusFrame);
    canvasFocusFrame = 0;
  }
  const startPanX = panX;
  const startPanY = panY;
  const startZoom = zoom;
  const start = performance.now();
  const duration = 220;
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    setCanvasView(
      startPanX + (targetPanX - startPanX) * eased,
      startPanY + (targetPanY - startPanY) * eased,
      startZoom + (targetZoom - startZoom) * eased
    );
    if (t < 1) {
      canvasFocusFrame = window.requestAnimationFrame(step);
    } else {
      canvasFocusFrame = 0;
    }
  };
  canvasFocusFrame = window.requestAnimationFrame(step);
}

function scrollSelectedNodeListItem() {
  if (!els.nodeList) return;
  window.requestAnimationFrame(() => {
    const active = Array.from(els.nodeList.querySelectorAll("[data-select-node]"))
      .find((item) => item.dataset.selectNode === selectedId);
    active?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
}

function focusCanvasNode(nodeId, { select = true, targetZoom = null } = {}) {
  const node = findNode(nodeId);
  if (!node || !els.canvasViewport) return;
  if (select) selectedId = nodeId;
  autoFitZoom = false;
  const targetZoomValue = targetZoom ? Math.max(0.7, Math.min(1.25, Number(targetZoom) || zoom)) : zoom;
  const box = els.canvasViewport.getBoundingClientRect();
  const nextPanX = box.width / 2 - (node.x + NODE_WIDTH / 2) * targetZoomValue;
  const nextPanY = box.height / 2 - (node.y + NODE_HEIGHT / 2) * targetZoomValue;
  renderNodeList();
  renderNodes();
  renderInspector();
  scrollSelectedNodeListItem();
  animateCanvasView(nextPanX, nextPanY, targetZoomValue);
}

function renderCanvasMinimap() {
  if (!els.canvasMinimap || !els.canvasViewport) return;
  const box = els.canvasViewport.getBoundingClientRect();
  const viewportWidth = box.width ? Math.min(100, (box.width / (CANVAS_WIDTH * zoom)) * 100) : 0;
  const viewportHeight = box.height ? Math.min(100, (box.height / (CANVAS_HEIGHT * zoom)) * 100) : 0;
  const viewportLeft = Math.max(0, Math.min(100 - viewportWidth, (-panX / (CANVAS_WIDTH * zoom)) * 100));
  const viewportTop = Math.max(0, Math.min(100 - viewportHeight, (-panY / (CANVAS_HEIGHT * zoom)) * 100));
  const nodes = orderedNodes()
    .map((node) => {
      const meta = nodeMeta[node.type] || {};
      return `
        <button
          type="button"
          class="minimap-node ${node.id === selectedId ? "active" : ""} ${statusClass(node.status)}"
          data-minimap-node="${escapeHtml(node.id)}"
          title="${escapeHtml(meta.label || node.id)}"
          style="
            left:${(node.x / CANVAS_WIDTH) * 100}%;
            top:${(node.y / CANVAS_HEIGHT) * 100}%;
            width:${(NODE_WIDTH / CANVAS_WIDTH) * 100}%;
            height:${(NODE_HEIGHT / CANVAS_HEIGHT) * 100}%;
          "
        ></button>
      `;
    })
    .join("");
  els.canvasMinimap.innerHTML = `
    <div class="minimap-title">小地图</div>
    <div class="minimap-stage">
      ${nodes}
      <span class="minimap-viewport" style="left:${viewportLeft}%;top:${viewportTop}%;width:${viewportWidth}%;height:${viewportHeight}%;"></span>
    </div>
  `;
}

function renderNodeList() {
  els.nodeList.innerHTML = orderedNodes()
    .map((node, index) => {
      const meta = nodeMeta[node.type];
      return `
        <button class="node-list-item ${node.id === selectedId ? "active" : ""}" data-select-node="${node.id}">
          <span class="node-list-name">
            <span class="node-dot ${meta.kind}"></span>
            <span>${index + 1}. ${meta.label}</span>
          </span>
          <span>${statusLabel(node.status)}</span>
        </button>
      `;
    })
    .join("");
}

function renderNodes() {
  const activeNodeIds = activeExecutionNodeIds();
  els.nodesLayer.innerHTML = orderedNodes()
    .map((node, index) => {
      const meta = nodeMeta[node.type];
      const isParallelActive = activeNodeIds.size > 1 && activeNodeIds.has(node.id);
      const highlights = getNodeHighlights(node)
        .map(([label, value]) => {
          return `<div class="node-value"><span>${label}</span><strong>${escapeHtml(value || "待填")}</strong></div>`;
        })
        .join("");
      const quickInput =
        node.type === "input"
          ? `<textarea class="node-quick-input" data-node-id="${node.id}" data-node-field="topic" placeholder="输入视频主题...">${escapeHtml(node.fields.topic)}</textarea>`
          : `<div class="node-values">${highlights}</div>`;

      return `
        <article
          class="workflow-node ${meta.kind} ${node.status} phase-${nodeVisualPhase(node)} ${isParallelActive ? "parallel-active" : ""} ${node.id === selectedId ? "selected" : ""}"
          data-node-id="${node.id}"
          style="transform: translate(${node.x}px, ${node.y}px);"
        >
          <span class="port in"></span>
          <span class="port out"></span>
          <div class="node-top" data-drag-node="${node.id}">
            <span class="node-index">${String(index + 1).padStart(2, "0")}</span>
            <div class="node-title-block">
              <div class="node-title">${meta.label}</div>
              <div class="node-type">${meta.type}</div>
            </div>
            <span class="status-dot"></span>
          </div>
          <div class="node-body">${quickInput}</div>
          <div class="node-footer">
            <div class="node-progress"><span style="width: ${node.progress}%"></span></div>
            <div class="node-status-text">${statusLabel(node.status)}</div>
          </div>
          <span class="node-scan"></span>
          <span class="node-burst"></span>
        </article>
      `;
    })
    .join("");
}

function renderLinks() {
  els.linkLayer.setAttribute("width", String(CANVAS_WIDTH));
  els.linkLayer.setAttribute("height", String(CANVAS_HEIGHT));
  els.linkLayer.setAttribute("viewBox", `0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`);
  els.linkLayer.setAttribute("preserveAspectRatio", "none");
  const visibleConnections = workflow.connections.filter((connection) => shouldRenderConnection(connection));
  const paths = visibleConnections
    .map((connection) => {
      const from = findNode(connection.from);
      const to = findNode(connection.to);
      if (!from || !to) return "";
      const outgoing = visibleConnections.filter((item) => item.from === from.id);
      const incoming = visibleConnections.filter((item) => item.to === to.id);
      const outIndex = Math.max(0, outgoing.findIndex((item) => item.id === connection.id));
      const inIndex = Math.max(0, incoming.findIndex((item) => item.id === connection.id));
      const lane = CONNECTION_LANE_OFFSETS[connection.id] || {};
      const sourceY = from.y + NODE_HEIGHT / 2 + (outIndex - (outgoing.length - 1) / 2) * 26 + Number(lane.sourceY || 0);
      const targetY = to.y + NODE_HEIGHT / 2 + (inIndex - (incoming.length - 1) / 2) * 26 + Number(lane.targetY || 0);
      const sourceX = from.x + NODE_WIDTH;
      const targetX = to.x;
      const curveFactor = Number(lane.curveFactor || 0.42);
      const curve = Math.max(70, Math.abs(targetX - sourceX) * curveFactor);
      const d = `M ${sourceX} ${sourceY} C ${sourceX + curve} ${sourceY}, ${targetX - curve} ${targetY}, ${targetX} ${targetY}`;
      const phase = connectionVisualPhase(connection);
      const className = `link-path ${connection.status || "idle"} phase-${phase}${lane.emphasize ? " link-emphasis" : ""}`;
      return `
        <path class="${className}" d="${d}" marker-end="url(#arrow)" />
        ${phase === "flowing" ? `<circle class="link-packet" r="4"><animateMotion dur="1.35s" repeatCount="indefinite" path="${d}" /></circle>` : ""}
      `;
    })
    .join("");

  els.linkLayer.innerHTML = `
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8da3c1"></path>
      </marker>
    </defs>
    ${paths}
  `;
}

function renderInspectorExtra(node) {
  if (!node) return "";
  if (node.id === "input") {
    const mode = currentRunMode();
    const fast = mode.includes("快速");
    return `
      <div class="inspector-extra-panel mode-panel ${fast ? "fast" : "final"}">
        <div class="mode-panel-head">
          <strong>${fast ? "快速预览模式" : "成片模式"}</strong>
          <span>${fast ? "试方向" : "正式输出"}</span>
        </div>
        <div class="mode-panel-grid">
          <div><small>分镜</small><strong>${escapeHtml(findNode("storyboard")?.fields?.shotCount || "-")} 镜</strong></div>
          <div><small>片段</small><strong>${escapeHtml(findNode("veo")?.fields?.parallel || "-")} 段</strong></div>
          <div><small>关键帧</small><strong>${escapeHtml(findNode("keyframe")?.fields?.frameCount || "-")} 张</strong></div>
        </div>
        <div class="field-help">${fast ? "适合先看题材和画面方向，成本更低、速度更快。" : "适合最终成片，会保留多片段衔接、首尾关键帧和较高质量配置。"}</div>
      </div>
    `;
  }
  if (node.id === "reference_input") {
    const mediaUrl = String(node.fields?.mediaUrl || "").trim();
    const localPath = String(node.fields?.localPath || "").trim();
    const mediaType = String(node.fields?.mediaType || "unknown").trim();
    const hasReference = Boolean(mediaUrl || localPath);
    const statusText = hasReference ? `已选择参考素材（${mediaType}）` : "尚未上传参考素材";
    return `
      <div class="inspector-extra-panel">
        <div class="field-group">
          <label>上传参考文件</label>
          <div class="reference-upload-row">
            <button type="button" class="rail-button compact" data-reference-upload-trigger>选择图片/视频</button>
            <input type="file" accept="image/*,video/*" data-reference-upload-input multiple hidden />
          </div>
          <div class="field-help">${escapeHtml(statusText)}</div>
        </div>
        ${renderReferenceVisualPanel(node)}
      </div>
    `;
  }
  if (node.id === "xhs_publish") {
    const status = providerStatus?.xhs || {};
    const connectState = status.cookieConfigured
      ? "Cookie 文件已找到"
      : (node.fields?.cookiePath || status.cookiePath)
        ? "Cookie 路径待检查"
        : "Cookie 未配置";
    return `
      <div class="inspector-extra-panel">
        <div class="field-group">
          <label>小红书发布配置说明</label>
          <div class="xhs-status-card">
            <span>${escapeHtml(connectState)}</span>
            <strong>${escapeHtml(status.baseUrl || node.fields?.baseUrl || "发布服务待配置")}</strong>
            <small>${escapeHtml(status.publishPath || node.fields?.publishPath || "发布路径待配置")}</small>
          </div>
          <button type="button" class="rail-button compact" data-xhs-test>连接测试</button>
          <div class="field-help">该步骤可选，不影响视频制作。建议先确认视频可下载，再开启自动发布。</div>
          <div class="xhs-guide-block">
            <div class="xhs-guide-title">配置顺序</div>
            <ol class="xhs-quick-steps">
              <li>在浏览器先登录小红书创作后台。</li>
              <li>用 Cookie Editor 导出 <code>cookies.json</code>（仅你自己的登录态）。</li>
              <li>把文件放到服务器本地，并在“Cookies 文件路径”填写绝对路径。</li>
              <li>先设置“可见范围”为仅自己可见，再把“自动发布开关”改为开启。</li>
            </ol>
          </div>
          <div class="xhs-guide-block">
            <div class="xhs-guide-title">字段模板（推荐）</div>
            <ul class="xhs-kv-list">
              <li><strong>Cookies 文件路径</strong><span>例如：<code>D:\\xhs\\cookies.json</code></span></li>
              <li><strong>发布服务地址</strong><span>例如：<code>http://127.0.0.1:9000</code></span></li>
              <li><strong>发布路径配置</strong><span>例如：<code>/api/publish/xiaohongshu</code></span></li>
              <li><strong>标签</strong><span>逗号分隔，不带 #，例如：<code>战马,历史,短片</code></span></li>
            </ul>
          </div>
          <div class="xhs-guide-block">
            <div class="xhs-guide-title">常见错误定位</div>
            <ul class="xhs-error-list">
              <li><strong>Cookie 失效</strong><span>重新登录小红书并导出新的 cookies.json。</span></li>
              <li><strong>发布服务不可达</strong><span>检查发布服务地址与发布路径配置拼接后的地址是否能访问。</span></li>
              <li><strong>发布失败</strong><span>先改“仅自己可见”做联调，确认成功后再切公开。</span></li>
            </ul>
          </div>
          <div class="field-help">联调建议：先关闭自动发布跑一轮；确认成片正常后，再开启自动发布。</div>
        </div>
      </div>
    `;
  }
  return "";
}

function modelCatalogFor(source) {
  const fallbackModels = (MODEL_FALLBACKS[source] || []).map((id) => ({
    id,
    label: `${id} · 常用候选`,
    qualityHint: id.includes("fast") || id.includes("mini") || id.includes("mute") ? "速度优先" : "质量候选",
  }));
  const catalog = providerModels?.[source];
  const fallbackModel =
    source === "gpt"
      ? providerStatus?.gpt?.model
      : source === "image"
        ? providerStatus?.image?.model
        : source === "veo"
          ? providerStatus?.veo?.model
          : providerStatus?.[source]?.model;
  const discovered = catalog && Array.isArray(catalog.models) ? catalog.models : [];
  const merged = [];
  [
    ...(fallbackModel ? [{ id: fallbackModel, label: `${fallbackModel} · 站内默认`, qualityHint: "默认" }] : []),
    ...discovered,
    ...fallbackModels,
  ].forEach((item) => {
    const id = String(item?.id || item?.model || item?.name || "").trim();
    if (!id || merged.some((option) => String(option?.id || option?.model || option?.name || "") === id)) return;
    merged.push({ ...item, id });
  });
  return merged;
}

function preferredQualityModel(source) {
  const models = modelCatalogFor(source);
  if (source === "veo") {
    return (
      models.find((item) => String(item?.id || "").includes("veo_3_1-4K")) ||
      models.find((item) => String(item?.id || "").includes("veo_3_1") && !String(item?.id || "").includes("fast")) ||
      models.find((item) => String(item?.qualityHint || "").includes("质量"))
    );
  }
  return models.find((item) => String(item?.qualityHint || "").includes("质量"));
}

function applyModelRecommendationsFromCatalog() {
  const input = findNode("input");
  const finalMode = String(input?.fields?.runMode || "成片模式") !== "快速预览";
  const veo = findNode("veo");
  if (!finalMode || !veo || veo.fields?.__modelLocked === "1") return false;
  const current = String(veo.fields?.model || "").toLowerCase();
  const preferred = preferredQualityModel("veo");
  if (!preferred?.id || !current.includes("fast")) return false;
  veo.fields.model = String(preferred.id);
  return true;
}

function modelOptionItems(node, field) {
  const baseOptions = Array.isArray(field.options)
    ? field.options.map((option) => ({ id: String(option), label: String(option) }))
    : [];
  const catalogOptions = field.modelSource
    ? modelCatalogFor(field.modelSource).map((item) => ({
        id: String(item?.id || item?.model || item?.name || "").trim(),
        label: String(item?.label || item?.id || item?.model || item?.name || "").trim(),
        qualityHint: String(item?.qualityHint || "").trim(),
      }))
    : [];
  const currentValue = String(node?.fields?.[field.key] || "").trim();
  const merged = [];
  [...(currentValue ? [{ id: currentValue, label: `${currentValue} · 当前` }] : []), ...catalogOptions, ...baseOptions].forEach((item) => {
    if (!item.id || merged.some((option) => option.id === item.id)) return;
    merged.push(item);
  });
  return merged;
}

function renderModelChooserPanel(node) {
  const modelFields = (fieldDefs[node.type] || []).filter((field) => field.modelSource);
  if (!modelFields.length) return "";
  const rows = modelFields.map((field) => {
    const current = String(node.fields?.[field.key] || "").trim() || "未选择";
    const catalog = providerModels?.[field.modelSource];
    const count = Array.isArray(catalog?.models) ? catalog.models.length : 0;
    const statusText = count
      ? `${count} 个可选模型`
      : catalog?.error
        ? catalog.error
        : "等待读取 baseurl 模型列表";
    return `
      <div class="model-source-row">
        <span>${escapeHtml(field.label)}</span>
        <strong>${escapeHtml(current)}</strong>
        <small>${escapeHtml(statusText)}</small>
      </div>
    `;
  }).join("");
  return `
    <div class="model-chooser-panel">
      <div class="model-chooser-head">
        <div>
          <span>模型选择</span>
          <small>来自 server/.env 里的 baseurl，不会把 API Key 写入前端。</small>
        </div>
        <button type="button" class="rail-button compact" data-refresh-provider-models>刷新模型</button>
      </div>
      ${rows}
    </div>
  `;
}

function renderInspector() {
  const node = findNode(selectedId) || workflow.nodes[0];
  const meta = nodeMeta[node.type];
  const fields = fieldDefs[node.type] || [];
  const fieldHtml = fields
    .map((field) => {
      const value = node.fields[field.key] ?? "";
      let control = "";
      const placeholder = field.placeholder ? ` placeholder="${escapeHtml(field.placeholder)}"` : "";
      if (field.type === "textarea") {
        control = `<textarea class="field-textarea" data-field="${field.key}"${placeholder}>${escapeHtml(value)}</textarea>`;
      } else if (field.type === "select") {
        const options = modelOptionItems(node, field);
        control = `
          <select class="field-select" data-field="${field.key}">
            ${options.map((option) => `<option value="${escapeHtml(option.id)}" ${String(option.id) === String(value) ? "selected" : ""}>${escapeHtml(option.label || option.id)}</option>`).join("")}
          </select>
        `;
      } else {
        control = `<input class="field-input" data-field="${field.key}" value="${escapeHtml(value)}" autocomplete="off"${placeholder} />`;
      }
      const help = field.help ? `<div class="field-help">${field.help}</div>` : "";
      return `
        <div class="field-group">
          <label>${field.label}</label>
          ${control}
          ${help}
        </div>
      `;
    })
    .join("");
  const extraPanel = renderInspectorExtra(node);
  const modelPanel = renderModelChooserPanel(node);

  els.inspectorContent.innerHTML = `
    <div class="inspector-title">
      <div>
        <div class="section-heading">${meta.type}</div>
        <h2>${meta.label}</h2>
      </div>
      <span class="status-pill ${statusClass(node.status)}">${statusLabel(node.status)}</span>
    </div>
    <div class="inspector-params-panel">
      <div class="inspector-params-head">
        <span>节点参数</span>
        <small>${fields.length} 项</small>
      </div>
      <div class="inspector-field-scroll">
        ${fieldHtml || `<div class="field-help">该节点暂无可调整参数。</div>`}
      </div>
    </div>
    ${modelPanel}
    ${extraPanel}
    <div class="node-output">
      <div class="section-heading">步骤产出</div>
      <div class="output-box">${renderNodeOutput(node)}</div>
    </div>
  `;
}

function renderPreview() {
  const input = findNode("input");
  const script = findNode("script");
  const storyboard = findNode("storyboard");
  const output = findNode("output");
  const topic = String(input.fields.topic || "").trim();
  const title = activeTask?.title || script?.output?.title || topic || "等待输入视频主题";
  const horse = input.fields.horse || "赤兔";
  const image = horseImages[horse] || horseImages["赤兔"];
  const videoUrl = getTaskVideoUrl(activeTask);
  const status = activeTask ? statusLabel(activeTask.status) : output.status === "done" ? "已生成" : isRunning ? "生成中" : "预览";
  const caption =
    activeTask?.result_payload?.note ||
    activeTask?.error_message ||
    (!topic
      ? "先在内容输入步骤填写主题，系统会匹配史料后整理画面描述。"
      : null) ||
    (output.status === "done"
      ? "当前任务已有结果返回，后续会继续接入真实成片地址。"
      : script?.output?.voiceover || input.fields.brief || "等待系统整理脚本与分镜");

  els.previewImage.src = image;
  if (els.previewVideo) {
    const frame = els.previewVideo.closest(".video-frame");
    if (videoUrl && activeTask?.status === "completed") {
      if (els.previewVideo.getAttribute("src") !== videoUrl) {
        els.previewVideo.setAttribute("src", videoUrl);
      }
      frame?.classList.add("has-video");
    } else {
      els.previewVideo.removeAttribute("src");
      els.previewVideo.load();
      frame?.classList.remove("has-video");
    }
  }
  els.previewTitle.textContent = title;
  els.previewHeadline.textContent = title;
  els.previewCaption.textContent = caption;
  els.previewAspect.textContent = input.fields.aspect || "9:16";
  els.previewStatus.textContent = status;
  els.previewStatus.className = `status-pill ${output.status === "done" ? "done" : isRunning ? "running" : "waiting"}`;

  const count = Number(storyboard.fields.shotCount || 5);
  const activeCount = storyboard.output?.shots?.length || 0;
  els.sceneStrip.innerHTML = Array.from({ length: Math.max(3, count) })
    .map((_, index) => {
      const shot = storyboard.output?.shots?.[index];
      return `<div class="scene-chip ${index < activeCount ? "active" : ""}">镜头 ${index + 1}<br>${escapeHtml(shot?.camera || "待生成")}</div>`;
    })
    .join("");
}

function renderStats() {
  els.nodeCount.textContent = String(workflow.nodes.length);
  els.linkCount.textContent = String(workflow.connections.filter((connection) => shouldRenderConnection(connection)).length);
  if (els.runtimeBadge) {
    const runtime = providerStatus?.runtime;
    const connected = Boolean(runtime?.enabled && runtime?.connected);
    const veoLimit = providerStatus?.veo?.maxClipsPerTask || findNode("veo")?.fields.parallel || 1;
    els.runtimeBadge.textContent = connected ? `状态同步已启用 / 并行制作 / 视频 ${veoLimit} 段` : "状态同步未连接";
    els.runtimeBadge.className = `runtime-badge ${connected ? "connected" : "offline"}`;
  }
  const doneCount = workflow.nodes.filter((node) => node.status === "done").length;
  if (activeTask) {
    els.workflowStatus.textContent = `${statusLabel(activeTask.status)} ${activeTask.progress || 0}%`;
  } else if (providerStatus) {
    const configured = ["gpt", "image", "veo"].filter((key) => providerStatus?.[key]?.configured).length;
    els.workflowStatus.textContent = isRunning
      ? `运行中 ${doneCount}/${workflow.nodes.length}`
      : `配置 ${configured}/3 就绪`;
  } else {
    els.workflowStatus.textContent = isRunning ? `运行中 ${doneCount}/${workflow.nodes.length}` : doneCount ? `已完成 ${doneCount}/${workflow.nodes.length}` : "待运行";
  }
  const input = findNode("input");
  const output = findNode("output");
  const script = findNode("script");
  const keyframe = findNode("keyframe");
  const veo = findNode("veo");
  const topic = String(input.fields.topic || "").trim();
  els.payloadSummary.textContent =
    activeTask?.result_payload?.videoUrl ||
    activeTask?.result_payload?.note ||
    (output.status === "done"
      ? "成片地址、字幕、音频和封面已写入输出步骤"
      : topic
        ? `${topic} / ${input.fields.duration}s / ${input.fields.aspect}`
        : "剧本创作 -> 关键帧 -> 视频片段 -> 成片输出");
}

function renderExecutionTimeline() {
  if (!els.executionTimeline) return;
  const states = runtimeNodeStateMap();
  const activeNodeIds = activeExecutionNodeIds();
  els.executionTimeline.innerHTML = orderedNodes()
    .map((node, index) => {
      const state = states.get(node.id);
      const status = normalizeNodeStatus(state?.status || node.status);
      const progress = Number(state?.progress ?? node.progress ?? 0);
      const meta = nodeMeta[node.type] || { label: node.id, kind: "text" };
      const phase = nodeVisualPhase({ ...node, status });
      const isCurrent = activeNodeIds.has(node.id);
      const isParallelActive = activeNodeIds.size > 1 && isCurrent;
      return `
        <button class="timeline-step ${status} phase-${phase} ${isCurrent ? "current" : ""} ${isParallelActive ? "parallel-active" : ""}" data-select-node="${node.id}">
          <span class="timeline-index">${index + 1}</span>
          <span class="timeline-copy">
            <strong>${escapeHtml(meta.label)}</strong>
            <small>${statusLabel(status)} · ${progress}%</small>
          </span>
          <span class="timeline-bar"><span style="width:${Math.max(0, Math.min(100, progress))}%"></span></span>
        </button>
      `;
    })
    .join("");
}

function renderExecutionPulse() {
  if (!els.executionPulse) return;
  const runtime = activeRuntimeState();
  const status = runtime?.status || activeTask?.status || (isRunning ? "processing" : "draft");
  const progress = Math.max(0, Math.min(100, Number(runtime?.progress ?? activeTask?.progress ?? 0)));
  const activeNodeIds = activeExecutionNodeIds();
  const activeLabels = [...activeNodeIds]
    .map((nodeId) => {
      const node = findNode(nodeId);
      return node ? nodeMeta[node.type]?.label || node.id : "";
    })
    .filter(Boolean);
  const currentNodeId = currentExecutionNodeId();
  const currentNode = currentNodeId ? findNode(String(currentNodeId).split(",")[0]) : null;
  const currentLabel = activeLabels.length > 1
    ? `${activeLabels.length} 个步骤并行`
    : activeLabels[0] || (currentNode ? nodeMeta[currentNode.type]?.label || currentNode.id : "等待运行");
  const active = ["queued", "processing"].includes(String(status));
  els.executionPulse.className = `execution-pulse ${active ? "active" : ""} ${statusClass(status)}`;
  els.executionPulse.innerHTML = `
    <span class="pulse-label">${escapeHtml(currentLabel)}</span>
    <span class="pulse-track">
      <span class="pulse-fill" style="width:${progress}%"></span>
      <span class="pulse-runner"></span>
    </span>
    <span class="pulse-percent">${progress}%</span>
  `;
}

function batchItemStatus(index) {
  const completed = generatedVideos.some((item) => Number(item.batchIndex || 0) === index);
  const failed = batchRunState?.failed?.some((item) => Number(item.index || 0) === index);
  if (completed) return "done";
  if (failed) return "failed";
  if (batchRunState?.running && Number(batchRunState.current || 0) === index) return "running";
  if (batchRunState && index < Number(batchRunState.current || 0)) return "skipped";
  return "queued";
}

function renderBatchQueue() {
  if (!els.batchQueue) return;
  const total = batchRunState?.total || targetVideoCount();
  const shouldShow = total > 1 || Boolean(batchRunState) || generatedVideos.length > 1;
  if (!shouldShow) {
    els.batchQueue.innerHTML = "";
    els.batchQueue.classList.remove("active");
    return;
  }
  els.batchQueue.classList.add("active");
  const doneCount = generatedVideos.length;
  const failedCount = batchRunState?.failed?.length || 0;
  const current = batchRunState?.current || (doneCount ? Math.min(doneCount + 1, total) : 1);
  const progressPercent = Math.max(0, Math.min(100, Math.round((doneCount / Math.max(1, total)) * 100)));
  const currentLabel = batchRunState?.running
    ? `正在生成第 ${current}/${total} 条`
    : doneCount >= total
      ? "批量已完成"
      : `等待第 ${Math.min(doneCount + 1, total)}/${total} 条`;
  els.batchQueue.innerHTML = `
    <div class="batch-queue-head">
      <div>
        <strong>批量任务队列</strong>
        <span>${doneCount}/${total} 已完成${failedCount ? `，${failedCount} 条失败` : ""}</span>
      </div>
      <button type="button" class="batch-skip-toggle ${batchQueueOptions.skipFailed ? "active" : ""}" data-batch-skip-toggle>
        ${batchQueueOptions.skipFailed ? "失败后跳过" : "失败后暂停"}
      </button>
    </div>
    <div class="batch-queue-track" aria-hidden="true">
      <span style="width:${progressPercent}%"></span>
    </div>
    <div class="batch-queue-overview">
      <b>${escapeHtml(currentLabel)}</b>
      <b>完成 ${doneCount}</b>
      <b>失败 ${failedCount}</b>
      <b>${batchQueueOptions.skipFailed ? "失败后继续" : "失败后暂停"}</b>
    </div>
    <div class="batch-queue-list">
      ${Array.from({ length: total }).map((_, offset) => {
        const index = offset + 1;
        const status = batchItemStatus(index);
        const video = generatedVideos.find((item) => Number(item.batchIndex || 0) === index);
        const failed = batchRunState?.failed?.find((item) => Number(item.index || 0) === index);
        const label = status === "done"
          ? "已完成"
          : status === "running"
            ? "正在生成"
            : status === "failed"
              ? "失败"
              : status === "skipped"
                ? "已跳过"
                : "排队中";
        const detail = video?.title || failed?.message || (status === "running" ? `正在处理第 ${current} 条` : "等待上一条完成");
        return `
          <div class="batch-queue-item ${status}">
            <span class="batch-queue-index">${String(index).padStart(2, "0")}</span>
            <div>
              <strong><span class="batch-queue-state">${escapeHtml(label)}</span></strong>
              <small>${escapeHtml(compactText(detail, 64))}</small>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function runtimeEventLabel(event) {
  const name = String(event?.event || "runtime");
  const labels = {
    "veo-clip-started": "视频片段开始",
    "veo-clip-submitted": "视频片段提交",
    "veo-clip-completed": "视频片段完成",
    "veo-clip-failed": "视频片段失败",
    "task-created": "任务创建",
    "workflow-queued": "进入队列",
    "workflow-started": "开始制作",
    "stage-started": "并行阶段开始",
    "parallel-nodes-started": "并行步骤开始",
    "parallel-nodes-completed": "并行步骤完成",
    "node-started": "步骤开始",
    "node-completed": "步骤完成",
    "workflow-completed": "制作完成",
    "workflow-failed": "制作失败",
    "workflow-cancelled": "制作取消",
    "workflow-cleared": "清空状态",
    inspection: "状态同步",
  };
  return labels[name] || name;
}

function renderRuntimeEvents() {
  if (!els.runtimeEvents) return;
  const events = activeRuntimeEvents().slice(-5).reverse();
  if (!events.length) {
    els.runtimeEvents.innerHTML = `<div class="runtime-event muted">制作动态会在开始后显示</div>`;
    return;
  }
  els.runtimeEvents.innerHTML = events
    .map((event) => {
      const payload = event?.payload && typeof event.payload === "object" ? event.payload : {};
      const nodeIds = Array.isArray(payload.nodeIds) ? payload.nodeIds : [];
      const nodeId = payload.nodeId || event.currentNode || "";
      const nodeLabel = nodeIds.length
        ? nodeIds
            .map((id) => {
              const node = findNode(id);
              return node ? nodeMeta[node.type]?.label || node.id : id;
            })
            .join(" + ")
        : (() => {
            const node = nodeId ? findNode(nodeId) : null;
            return node ? nodeMeta[node.type]?.label || node.id : nodeId;
          })();
      const time = event?.at ? new Date(event.at).toLocaleTimeString("zh-CN", { hour12: false }) : "";
      const status = statusLabel(event?.status || "");
      return `
        <div class="runtime-event ${statusClass(event?.status || "")}">
          <span>${escapeHtml(time)}</span>
          <strong>${escapeHtml(runtimeEventLabel(event))}</strong>
          <small>${escapeHtml([nodeLabel, status].filter(Boolean).join(" · "))}</small>
        </div>
      `;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderJsonOutput(output) {
  return `<pre class="output-json">${escapeHtml(formatOutput(output))}</pre>`;
}

function keyframeOutputImages(output) {
  const images = Array.isArray(output?.images) ? output.images : [];
  const fallbackHorse = findNode("input")?.fields?.horse || "";
  const fallbackUrl = horseImages[fallbackHorse] || horseImages["赤兔"] || horseImages["璧ゅ厰"] || "../images/chitu.png";
  return images
    .map((item, index) => {
      const rawUrl = item?.imageUrl ?? item?.url;
      const imageUrl = safeMediaUrl(rawUrl) || safeMediaUrl(item?.fallbackUrl) || safeMediaUrl(fallbackUrl);
      const scene = Number.isFinite(Number(item?.scene)) ? Number(item.scene) : index + 1;
      const cacheMode = String(item?.cacheMode || "");
      const reusedFromScene = Number.isFinite(Number(item?.reusedFromScene)) ? Number(item.reusedFromScene) : 0;
      const prompt = String(item?.prompt || "").trim();
      const providerError = String(item?.providerError || item?.error || "").trim();
      const isPending = String(rawUrl || "").startsWith("pending://") || String(item?.status || "").toLowerCase() === "pending";
      const rawRole = String(item?.frameRole || item?.role || "").trim().toLowerCase();
      const frameRole = rawRole.includes("end") || rawRole.includes("tail")
        ? "尾帧"
        : rawRole.includes("start") || rawRole.includes("head")
          ? "首帧"
          : "";
      return {
        scene,
        imageUrl,
        cacheMode,
        reusedFromScene,
        prompt,
        frameRole,
        providerError,
        isPending,
        pendingUrl: isPending ? String(rawUrl || "") : "",
      };
    })
    .filter(Boolean);
}

function renderKeyframeOutput(output) {
  const images = keyframeOutputImages(output);
  if (!images.length) {
    return renderJsonOutput(output);
  }
  const cards = images
    .map((item) => {
      const sceneLabel = `Scene ${item.scene}${item.frameRole ? ` · ${item.frameRole}` : ""}`;
      const sourceLabel = item.reusedFromScene
        ? `复用 Scene ${item.reusedFromScene} 尾帧`
        : item.cacheMode === "hit"
          ? "缓存命中"
          : "新生成";
      const prompt = item.prompt ? `<p>${escapeHtml(item.prompt)}</p>` : "";
      return `
        <figure class="output-image-card">
          <a class="output-image-link" href="${escapeHtml(item.imageUrl)}" target="_blank" rel="noopener">
            <img src="${escapeHtml(item.imageUrl)}" alt="${escapeHtml(`关键帧 ${sceneLabel}`)}" loading="lazy" />
          </a>
          <figcaption>
            <strong>${escapeHtml(sceneLabel)}</strong>
            <span>${escapeHtml(sourceLabel)}</span>
            ${prompt}
          </figcaption>
        </figure>
      `;
    })
    .join("");
  return `<div class="output-image-grid">${cards}</div>`;
}

function renderNodeOutput(node) {
  if (!node?.output) {
    return `<div class="output-empty">等待该步骤处理。</div>`;
  }
  if (node.type === "keyframe") {
    return renderKeyframeOutput(node.output);
  }
  return renderJsonOutput(node.output);
}

function compactText(value, maxLength = 120) {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function hasOutput(node) {
  return Boolean(node?.output && typeof node.output === "object" && Object.keys(node.output).length);
}

function nodeOutputOptional(node) {
  if (!node) return false;
  if (node.type === "input") return true;
  if (node.type === "reference_input" && !optionEnabled(node?.fields?.enabled)) return true;
  if (node.type === "reference_analyze" && !optionEnabled(findNode("reference_input")?.fields?.enabled)) return true;
  if (node.type === "xhs_publish" && !optionEnabled(node?.fields?.enabled)) return true;
  return false;
}

function nodeMissingPrimaryOutput(node) {
  const status = normalizeNodeStatus(node?.status);
  const workflowSettled = Boolean(
    activeTask && !["draft", "queued", "processing"].includes(String(activeTask.status || ""))
  );
  if (!workflowSettled && status !== "failed") return false;
  if (status !== "done" && status !== "failed") return false;
  if (hasOutput(node)) return false;
  if (nodeOutputOptional(node)) return false;
  return true;
}

function nodeFailureHint(node) {
  const status = normalizeNodeStatus(node?.status);
  if (status === "failed") {
    const errorText = compactText(
      node?.output?.error || node?.output?.providerError || activeTask?.error_message || "步骤处理失败，请查看日志。",
      170
    );
    return {
      level: "failed",
      chip: "处理失败",
      message: `故障定位：${errorText}`,
    };
  }
  if (nodeMissingPrimaryOutput(node)) {
    const nodeLabel = nodeMeta[node.type]?.label || node.id;
    return {
      level: "attention",
      chip: "疑似空输出",
      message: `故障定位：${nodeLabel} 已结束但无主要输出，请优先检查该步骤配置与上游输入。`,
    };
  }
  return null;
}

function renderBriefChips(chips) {
  const safe = asList(chips)
    .map((item) => compactText(item, 28))
    .filter(Boolean);
  if (!safe.length) return "";
  return `
    <div class="brief-chip-row">
      ${safe.map((item) => `<span class="brief-chip">${escapeHtml(item)}</span>`).join("")}
    </div>
  `;
}

function renderBriefLines(lines, options = {}) {
  const { clamp = 3, maxLength = 170 } = options;
  const safe = asList(lines)
    .map((item) => compactText(item, maxLength))
    .filter(Boolean);
  if (!safe.length) return "";
  return `
    <ul class="brief-line-list" style="--brief-line-clamp:${Number(clamp) || 3};">
      ${safe.map((item) => `<li title="${escapeHtml(item)}">${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function renderBriefImages(images) {
  const safe = asList(images).slice(0, 4);
  if (!safe.length) return "";
  return `
    <div class="brief-image-grid">
      ${safe
        .map((item) => {
          const imageUrl = safeMediaUrl(item?.url);
          if (!imageUrl) return "";
          const label = compactText(item?.label || "", 26);
          const note = compactText(
            item?.providerError
              ? `图片接口失败：${item.providerError}`
              : item?.isPending
                ? "图片生成接口未返回真实图片，当前显示兜底参考图。"
                : "",
            120
          );
          return `
            <figure class="brief-image-item ${item?.isPending ? "pending" : ""}">
              <a href="${escapeHtml(imageUrl)}" target="_blank" rel="noopener">
                <img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(label || "node media")}" loading="lazy" />
              </a>
              ${(label || note) ? `<figcaption>${label ? `<span>${escapeHtml(label)}</span>` : ""}${note ? `<small>${escapeHtml(note)}</small>` : ""}</figcaption>` : ""}
            </figure>
          `;
        })
        .join("")}
    </div>
  `;
}

function normalizeTextLine(value, maxLength = 120) {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  return compactText(text, maxLength);
}

function collectSubtitleLines(output) {
  const rawSegments = asList(output?.segments || output?.subtitleSegments);
  const lines = rawSegments
    .map((item) => {
      if (typeof item === "string") return normalizeTextLine(item, 60);
      return normalizeTextLine(item?.text || item?.subtitle || item?.narration || "", 60);
    })
    .filter(Boolean);
  if (lines.length) return lines;

  const storyboardShots = asList(findNode("storyboard")?.output?.shots);
  const scriptShots = asList(findNode("script")?.output?.shots);
  const fallbackLines = [...storyboardShots, ...scriptShots]
    .map((shot) => normalizeTextLine(shot?.subtitle || shot?.narration || "", 60))
    .filter(Boolean);
  return fallbackLines;
}

function outputMetric(label, value) {
  const text = compactText(value, 36);
  if (!text) return "";
  return `<span class="brief-metric"><small>${escapeHtml(label)}</small><strong>${escapeHtml(text)}</strong></span>`;
}

function renderBriefMetrics(metrics) {
  const html = asList(metrics)
    .map((item) => outputMetric(item?.label, item?.value))
    .filter(Boolean)
    .join("");
  return html ? `<div class="brief-metric-row">${html}</div>` : "";
}

function outputLink(label, url) {
  const safeUrl = String(url || "").trim();
  if (!safeUrl) return "";
  return `
    <a class="brief-output-link" href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(compactText(safeUrl, 48))}</strong>
    </a>
  `;
}

function firstArtifactUrl(output) {
  if (!output || typeof output !== "object") return "";
  return (
    safeMediaUrl(output.videoUrl) ||
    safeMediaUrl(output.finalVideoUrl) ||
    safeMediaUrl(output.subtitleUrl) ||
    safeMediaUrl(output.audioUrl) ||
    safeMediaUrl(output.voiceUrl) ||
    safeMediaUrl(output.coverUrl) ||
    safeMediaUrl(output.imageUrl) ||
    safeMediaUrl(asList(output.images)[0]?.url) ||
    safeMediaUrl(asList(output.clips)[0]?.videoUrl || asList(output.clips)[0]?.url)
  );
}

function observationMetrics(node) {
  const output = node.output || {};
  const state = node.runtimeState || {};
  const retryCount =
    output.retryCount ?? output.retries ?? output.retry_count ?? state.retryCount ?? state.retries ?? "";
  const elapsed =
    output.elapsedSeconds ??
    output.elapsed_seconds ??
    output.durationSeconds ??
    output.duration_seconds ??
    state.elapsedSeconds ??
    state.elapsed_seconds ??
    "";
  return [
    { label: "状态", value: statusLabel(node.status) },
    { label: "进度", value: Number(node.progress || 0) ? `${Number(node.progress || 0)}%` : "" },
    { label: "重试", value: retryCount !== "" && retryCount !== null && retryCount !== undefined ? `${retryCount} 次` : "" },
    { label: "耗时", value: elapsed ? `${elapsed}s` : "" },
  ];
}

function observationLines(node) {
  const output = node.output || {};
  const state = node.runtimeState || {};
  return [
    output.inputSummary || output.input_summary || state.inputSummary || state.input_summary
      ? `输入摘要：${output.inputSummary || output.input_summary || state.inputSummary || state.input_summary}`
      : "",
    output.error || output.providerError || state.error
      ? `失败原因：${output.error || output.providerError || state.error}`
      : "",
  ].filter(Boolean);
}

function renderBriefArtifacts(node) {
  const url = firstArtifactUrl(node.output || {});
  if (!url) return "";
  return `<div class="brief-artifact-row">${outputLink("最终产物", url)}</div>`;
}

function firstRagReference(output) {
  const refs = asList(output?.ragReferences || output?.promptSeed?.references);
  return refs.find((item) => item && typeof item === "object") || null;
}

function ragReferenceLines(ref) {
  if (!ref) return [];
  return [
    ref.story ? `知识库摘要：${ref.story}` : "",
    ref.ownerLifeStory ? `主人线索：${ref.ownerLifeStory}` : "",
    ref.horseLifeStory ? `名马线索：${ref.horseLifeStory}` : "",
  ].filter(Boolean);
}

function storyboardManifestLines(manifest, limit = 4) {
  if (!manifest || typeof manifest !== "object") return [];
  const frames = asList(manifest.frames);
  const header = frames.length ? `StoryboardFrame: ${frames.length} 镜 / 预计 ${Number(manifest.plannedDuration || 0).toFixed(1)}s` : "";
  const promptPlan = manifest.promptPlan && typeof manifest.promptPlan === "object" ? manifest.promptPlan : {};
  const planLine = promptPlan.imagePrompts || promptPlan.videoPrompts ? "Pixelle-style: narration -> image prompt -> video prompt" : "";
  const frameLines = frames.slice(0, limit).map((frame) => {
    const scene = frame.scene || Number(frame.index || 0) + 1;
    const dur = frame.plannedDuration ? `${frame.plannedDuration}s` : "";
    const status = frame.status && frame.status !== "planned" ? ` / ${frame.status}` : "";
    const text = compactText(frame.subtitle || frame.narration || frame.imagePrompt || "", 58);
    return `S${scene} ${dur}${status} ${text}`.trim();
  });
  return [header, planLine, ...frameLines].filter(Boolean);
}

function reviewReportLines(report) {
  if (!report || typeof report !== "object") return [];
  const checks = asList(report.checks);
  const failed = asList(report.failedChecks);
  const summary = report.summary ? `质检: ${report.status || "unknown"} / ${report.summary}` : "";
  const checkLine = checks.length ? `检查项: ${checks.filter((item) => item?.passed).length}/${checks.length} 通过` : "";
  const failedLine = failed.length ? `需关注: ${failed.join("、")}` : "";
  return [summary, checkLine, failedLine].filter(Boolean);
}

function nodeBriefModel(node) {
  const output = node.output || {};
  const fields = node.fields || {};

  if (node.type === "reference_input") {
    const mediaUrl = String(fields.mediaUrl || "").trim();
    const localPath = String(fields.localPath || "").trim();
    const hasReference = Boolean(mediaUrl || localPath);
    const imageUrl = safeMediaUrl(mediaUrl);
    return {
      title: compactText(hasReference ? "参考素材已配置" : "参考素材上传", 80),
      chips: [fields.enabled || "关闭", fields.sourceType || "上传文件", fields.mediaType || "unknown"],
      lines: [mediaUrl, localPath, fields.note].filter(Boolean),
      images: fields.mediaType === "image" && imageUrl ? [{ url: imageUrl, label: "参考图" }] : [],
    };
  }

  if (node.type === "reference_analyze") {
    return {
      title: compactText(output.summary || "参考风格分析", 80),
      chips: [fields.model || "gpt", output.analysisMode || "", output.mediaType || ""],
      lines: [
        output.visualStyle,
        output.cameraLanguage,
        output.lighting,
        output.motion,
        output.negative,
      ],
      images: output.source?.frameUrl ? [{ url: output.source.frameUrl, label: "视频首帧" }] : [],
    };
  }

  if (node.type === "input") {
    return {
      title: compactText(fields.topic || "等待输入主题", 80),
      chips: [fields.horse, fields.runMode || "成片模式", `${fields.duration || 0}s`, fields.aspect],
      lines: [fields.brief, fields.audience].filter(Boolean),
      metrics: [
        { label: "数量", value: `${fields.videoCount || 1} 条` },
        { label: "模式", value: fields.runMode || "成片模式" },
      ],
      images: [],
    };
  }

  if (node.type === "script") {
    const shots = asList(output.shots);
    const shotNarrations = shots.slice(0, 3).map((shot) => shot?.narration || shot?.subtitle).filter(Boolean);
    const ref = firstRagReference(output);
    const manifestLines = storyboardManifestLines(output.storyboardManifest, 3);
    return {
      title: compactText(output.title || "剧本内容", 80),
      chips: [fields.model, output.ragMatched ? "已命中马库" : "", shots.length ? `${shots.length} 镜头` : "", fields.style],
      lines: [output.voiceover, ...manifestLines, ...shotNarrations, ...ragReferenceLines(ref), output.note],
      metrics: [
        { label: "马库", value: output.ragMatched ? ref?.name || "已命中" : "未命中" },
        { label: "模型", value: output.model || fields.model },
      ],
      images: [],
    };
  }

  if (node.type === "storyboard") {
    const shots = asList(output.shots);
    const manifestLines = storyboardManifestLines(output.storyboardManifest, 5);
    const shotLines = shots.slice(0, 3).map((shot, index) => {
      const scene = Number.isFinite(Number(shot?.scene)) ? Number(shot.scene) : index + 1;
      const camera = compactText(shot?.camera || "", 42);
      const subtitle = compactText(shot?.subtitle || shot?.narration || "", 56);
      return `S${scene} ${camera}${subtitle ? ` | ${subtitle}` : ""}`.trim();
    });
    return {
      title: compactText(output.storyTitle || output.title || "分镜拆解", 80),
      chips: [shots.length ? `${shots.length} 镜` : "", `${fields.shotSeconds || ""}s/镜`, fields.promptLanguage],
      lines: manifestLines.length ? manifestLines : (shotLines.length ? shotLines : [output.note]),
      metrics: [
        { label: "分镜", value: `${shots.length || fields.shotCount || 0} 镜` },
        { label: "节奏", value: `${fields.shotSeconds || ""} 秒/镜` },
      ],
      images: [],
    };
  }

  if (node.type === "voice") {
    const segments = asList(output.segments);
    const audioUrl = safeMediaUrl(output.audioUrl || output.voiceUrl || output.narrationUrl);
    return {
      title: compactText(output.voiceover || output.narration || "配音规划", 80),
      chips: [fields.voice, fields.emotion, segments.length ? `${segments.length} 段` : ""],
      lines: [...segments.slice(0, 4).map((item) => item?.text), audioUrl ? "音频已生成" : ""],
      images: [],
    };
  }

  if (node.type === "keyframe") {
    const images = keyframeOutputImages(output);
    const manifestLines = storyboardManifestLines(output.storyboardManifest, 3);
    const imageErrors = images
      .map((item) => item.providerError
        ? `图片接口失败：${item.providerError}`
        : item.isPending
          ? "图片生成接口未返回真实图片，当前显示兜底参考图。"
          : "")
      .filter(Boolean);
    return {
      title: compactText(output.promptStyle || fields.promptStyle || "关键帧生成", 80),
      chips: [images.length ? `${images.length} 张` : "", output.referenceMode || fields.referenceMode, output.imageSize || fields.imageSize],
      lines: [...manifestLines, ...imageErrors, ...images.slice(0, 3).map((item) => item?.prompt)],
      metrics: [
        { label: "图片", value: `${images.length || 0} 张` },
        { label: "策略", value: output.referenceMode || fields.referenceMode },
      ],
      images: images.map((item) => ({
        url: item.imageUrl,
        label: `Scene ${item.scene}${item.frameRole ? ` ${item.frameRole}` : ""}`,
        providerError: item.providerError,
        isPending: item.isPending,
      })),
    };
  }

  if (node.type === "subtitle") {
    const segments = asList(output.segments || output.subtitleSegments);
    return {
      title: compactText("字幕规划", 80),
      chips: [output.style || fields.style, output.language || fields.language, segments.length ? `${segments.length} 行` : ""],
      lines: segments.slice(0, 5).map((item) => item?.text),
      images: [],
    };
  }

  if (node.type === "veo") {
    const clips = asList(output.clips);
    const manifestLines = storyboardManifestLines(output.storyboardManifest, 4);
    return {
      title: compactText(output.summary || "视频片段生成", 80),
      chips: [fields.model, clips.length ? `${clips.length} 段` : "", fields.aspect],
      lines: [
        ...manifestLines,
        clips[0]?.prompt,
        clips[0]?.narration,
        clips[1]?.prompt,
        clips[1]?.narration,
        output.durationStrategy,
      ],
      metrics: [
        { label: "成功", value: output.successfulClipCount ?? clips.length },
        { label: "并行", value: output.parallelExecution?.workers ? `${output.parallelExecution.workers} 路` : "未启用" },
        { label: "模式", value: currentRunMode() },
      ],
      images: [],
    };
  }

  if (node.type === "compose") {
    const sourceClips = asList(output.sourceClips);
    const reviewLines = reviewReportLines(output.reviewReport);
    const manifestLines = storyboardManifestLines(output.storyboardManifest, 3);
    return {
      title: compactText(output.videoUrl ? "成片合成完成" : "视频合成", 80),
      chips: [sourceClips.length ? `${sourceClips.length} 段合成` : "", output.compositionMode || "", output.subtitleStyle || ""],
      lines: [...reviewLines, ...manifestLines, output.note, output.subtitleUrl],
      metrics: [
        { label: "片段", value: `${sourceClips.length || 0} 段` },
        { label: "字幕", value: output.subtitleUrl ? "已烧录/挂载" : "待生成" },
      ],
      images: [],
    };
  }

  if (node.type === "xhs_publish") {
    const cookiePath = String(fields.cookiePath || "").trim();
    const endpoint = compactText(String(output.endpoint || "").trim(), 66);
    const errorMessage = compactText(String(output.error || "").trim(), 72);
    const publishMode = String(output.publishMode || fields.publishMode || "direct").trim();
    const scheduledAt = compactText(String(output.scheduledAt || fields.scheduledAt || "").trim(), 60);
    const autoCommentStatus = String(output.autoComment?.status || "").trim();
    const commentsCollectStatus = String(output.commentsCollection?.status || "").trim();
    const commentsCollectCount = Number(output.commentsCollection?.count || 0);
    return {
      title: compactText(output.message || "小红书自动发布", 80),
      chips: [fields.enabled || "关闭", output.status || "待处理", publishMode, fields.visibility || "公开可见"],
      lines: [
        cookiePath ? "Cookie：已配置" : "Cookie：未配置（该步骤会自动跳过）",
        scheduledAt ? `定时：${scheduledAt}` : "",
        endpoint ? `发布路径：${endpoint}` : "",
        autoCommentStatus ? `自动评论：${autoCommentStatus}` : "",
        commentsCollectStatus ? `评论采集：${commentsCollectStatus}` : "",
        commentsCollectStatus ? `采集条数：${commentsCollectCount}` : "",
        errorMessage ? `错误：${errorMessage}` : "",
      ].filter(Boolean),
      images: [],
    };
  }

  const sourceClips = asList(output.sourceClips);
  const reviewLines = reviewReportLines(output.reviewReport);
  const manifestLines = storyboardManifestLines(output.storyboardManifest, 3);
  return {
    title: compactText(output.videoUrl ? "成片已输出" : "输出步骤", 80),
    chips: [output.aspect || fields.aspect, output.duration ? `${output.duration}s` : "", sourceClips.length ? `${sourceClips.length} 段来源` : ""],
    lines: [...reviewLines, ...manifestLines, output.videoUrl, output.subtitleUrl, output.note],
    metrics: [
      { label: "成片库", value: generatedVideos.length ? `${generatedVideos.length} 条` : "" },
      { label: "下载", value: output.videoUrl ? "可用" : "" },
    ],
    images: [],
  };
}

function nodeBriefModelV2(node) {
  const output = node.output || {};
  const fields = node.fields || {};

  if (node.type === "voice") {
    const expectedSoundscape = normalizeTextLine(
      output.soundscape || fields.soundscape || "马蹄声、环境风声、战场氛围音，旁白清晰靠前",
      72
    );
    const expectedVoice = normalizeTextLine(
      output.voiceStyle || `${fields.voice || "中文音色"}，语速 ${fields.speed || "1.0"}x`,
      72
    );
    const expectedEmotion = normalizeTextLine(
      output.emotion || fields.emotion || "庄重、克制、有力量感的中文口语旁白",
      72
    );
    const audioReady = safeMediaUrl(output.audioUrl || output.voiceUrl || output.narrationUrl);
    return {
      title: compactText("声音预期效果", 80),
      chips: [fields.mode || "中文配音优先", fields.engine || "中文配音", fields.voice || "中文音色"],
      lines: [
        `旁白风格：${expectedEmotion}`,
        `音色与语速：${expectedVoice}`,
        `环境音层：${expectedSoundscape}`,
        audioReady ? "状态：音频已生成，可用于合成" : "状态：等待音频生成",
      ],
      metrics: [
        { label: "语速", value: `${fields.speed || "1.0"}x` },
        { label: "口语", value: "中文" },
      ],
      images: [],
    };
  }

  if (node.type === "subtitle") {
    const subtitleLines = collectSubtitleLines(output).slice(0, 8);
    return {
      title: compactText("字幕内容", 80),
      chips: [output.style || fields.style || "标准样式", output.language || fields.language || "简体中文"],
      lines: subtitleLines.length
        ? subtitleLines.map((line, index) => `${index + 1}. ${line}`)
        : ["暂无字幕内容，等待字幕步骤完成"],
      metrics: [
        { label: "字幕行", value: subtitleLines.length ? `${subtitleLines.length} 行` : "" },
        { label: "单行", value: `${fields.maxChars || 18} 字` },
      ],
      images: [],
    };
  }

  return nodeBriefModel(node);
}

function reviewCardLabel(node) {
  const labels = {
    reference_input: "参考卡",
    reference_analyze: "风格卡",
    input: "主题卡",
    script: "剧本卡",
    storyboard: "分镜卡",
    keyframe: "关键帧卡",
    voice: "声音卡",
    subtitle: "字幕卡",
    veo: "Veo 片段卡",
    compose: "合成卡",
    output: "成片卡",
    xhs_publish: "发布卡",
  };
  return labels[node?.type] || "节点卡";
}

function renderReviewTextBlock(title, lines, { clamp = 0 } = {}) {
  const safeLines = asList(lines).map((line) => normalizeTextLine(line, 260)).filter(Boolean);
  if (!safeLines.length) return "";
  const visibleLines = clamp ? safeLines.slice(0, clamp) : safeLines;
  return `
    <section class="review-block">
      <h4>${escapeHtml(title)}</h4>
      ${visibleLines.map((line) => `<p>${escapeHtml(line)}</p>`).join("")}
    </section>
  `;
}

function renderStoryboardManifestDetail(manifest, { clamp = 10 } = {}) {
  if (!manifest || typeof manifest !== "object") return "";
  const frames = asList(manifest.frames);
  const lines = frames.map((frame, index) => {
    const scene = frame.scene || index + 1;
    const duration = frame.plannedDuration ? `${frame.plannedDuration}s` : "";
    const text = frame.subtitle || frame.narration || frame.imagePrompt || "";
    const artifactCount = Object.keys(frame.artifacts || {}).length;
    return `S${scene} ${duration} ${frame.status || "planned"} / artifacts ${artifactCount}: ${text}`;
  });
  return renderReviewTextBlock("Storyboard Frame Manifest", lines, { clamp });
}

function renderReviewReportDetail(report) {
  if (!report || typeof report !== "object") return "";
  const checks = asList(report.checks);
  const lines = [
    report.summary ? `${report.status || "unknown"}: ${report.summary}` : "",
    ...checks.map((check) => `${check?.passed ? "PASS" : "CHECK"} ${check?.name || ""}${check?.detail ? ` / ${check.detail}` : ""}`),
  ];
  return renderReviewTextBlock("Workflow Review Report", lines, { clamp: 12 });
}

function renderReviewShotCards(shots) {
  const safeShots = asList(shots).slice(0, 8);
  if (!safeShots.length) return "";
  return `
    <section class="review-block">
      <h4>分镜内容</h4>
      <div class="review-shot-list">
        ${safeShots.map((shot, index) => `
          <div class="review-shot-card">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong>${escapeHtml(compactText(shot?.title || shot?.sceneTitle || `分镜 ${index + 1}`, 46))}</strong>
            <p>${escapeHtml(compactText(shot?.narration || shot?.voiceover || shot?.subtitle || "", 160))}</p>
            <small>${escapeHtml(compactText(shot?.camera || shot?.visual || shot?.prompt || "", 120))}</small>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

function renderReviewLinkList(title, items) {
  const safeItems = asList(items)
    .map((item, index) => {
      const url = safeMediaUrl(item?.videoUrl || item?.url || item?.audioUrl || item?.imageUrl || item);
      if (!url) return "";
      return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(item?.label || item?.title || `产物 ${index + 1}`)}</a>`;
    })
    .filter(Boolean);
  if (!safeItems.length) return "";
  return `
    <section class="review-block">
      <h4>${escapeHtml(title)}</h4>
      <div class="review-link-list">${safeItems.join("")}</div>
    </section>
  `;
}

function renderNodeReviewDetail(node) {
  const output = node.output || {};
  const fields = node.fields || {};
  if (node.type === "reference_input") {
    const assets = referenceAssetsFromFields(fields);
    return `
      ${renderReviewTextBlock("参考策略", [
        `主体 ${referenceWeightsFromFields(fields).normalized.subject}% / 风格 ${referenceWeightsFromFields(fields).normalized.style}% / 镜头 ${referenceWeightsFromFields(fields).normalized.camera}%`,
        fields.note,
      ])}
      ${renderReviewLinkList("素材链接", assets.map((asset, index) => ({ ...asset, label: asset.name || `素材 ${index + 1}` })))}
    `;
  }
  if (node.type === "script") {
    return `
      ${renderReviewTextBlock("完整旁白", [output.voiceover || output.narration || output.script || fields.customPrompt])}
      ${renderStoryboardManifestDetail(output.storyboardManifest, { clamp: 8 })}
      ${renderReviewShotCards(output.shots)}
    `;
  }
  if (node.type === "storyboard") {
    return `
      ${renderStoryboardManifestDetail(output.storyboardManifest, { clamp: 8 })}
      ${renderReviewTextBlock("分镜策略", [fields.visualStyle, fields.camera, fields.promptGuidance])}
      ${renderReviewShotCards(output.shots)}
    `;
  }
  if (node.type === "keyframe") {
    const images = keyframeOutputImages(output);
    return `
      ${renderStoryboardManifestDetail(output.storyboardManifest, { clamp: 8 })}
      ${renderBriefImages(images.map((item) => ({ url: item.imageUrl, label: `S${item.scene} ${item.frameRole || "关键帧"}` })))}
      ${renderReviewTextBlock("关键帧提示词", images.map((item) => item.prompt), { clamp: 6 })}
    `;
  }
  if (node.type === "subtitle") {
    return renderReviewTextBlock("字幕全文", collectSubtitleLines(output), { clamp: 12 });
  }
  if (node.type === "voice") {
    return renderReviewTextBlock("声音预期", [
      output.voiceover || output.narration,
      output.soundscape || fields.soundscape,
      output.emotion || fields.emotion,
      `语速 ${fields.speed || "1.0"}x / 音色 ${fields.voice || "中文音色"}`,
    ]);
  }
  if (node.type === "veo") {
    const clips = asList(output.clips);
    return `
      ${renderStoryboardManifestDetail(output.storyboardManifest, { clamp: 8 })}
      ${renderReviewTextBlock("片段提示词", clips.map((clip, index) => `片段 ${index + 1}: ${clip?.prompt || clip?.narration || ""}`), { clamp: 8 })}
      ${renderReviewLinkList("片段产物", clips.map((clip, index) => ({ ...clip, label: `Veo 片段 ${index + 1}` })))}
    `;
  }
  if (node.type === "compose" || node.type === "output") {
    return `
      ${renderReviewReportDetail(output.reviewReport)}
      ${renderStoryboardManifestDetail(output.storyboardManifest, { clamp: 8 })}
      ${renderReviewTextBlock("成片信息", [output.note, output.videoUrl, output.subtitleUrl])}
      ${renderReviewLinkList("可打开产物", [
        { label: "成片视频", videoUrl: output.videoUrl || output.finalVideoUrl },
        { label: "字幕文件", url: output.subtitleUrl },
        { label: "封面", imageUrl: output.coverUrl },
      ])}
    `;
  }
  if (node.type === "xhs_publish") {
    return renderReviewTextBlock("发布检查", [
      output.message,
      output.endpoint,
      output.autoComment?.status ? `自动评论：${output.autoComment.status}` : "",
      output.commentsCollection?.status ? `评论采集：${output.commentsCollection.status}` : "",
    ]);
  }
  return renderReviewTextBlock("节点内容", asList(nodeBriefModel(node).lines), { clamp: 8 });
}

function renderNodeBriefCard(node, index) {
  const history = asList(nodeOutputHistory[node.id]);
  const issue = nodeFailureHint(node);
  const shouldShow =
    node.type === "input" ||
    node.type === "reference_input" ||
    node.type === "xhs_publish" ||
    hasOutput(node) ||
    node.status === "failed" ||
    nodeMissingPrimaryOutput(node) ||
    history.length > 0 ||
    (node.id === "output" && generatedVideos.length > 0) ||
    Boolean(issue);
  if (!shouldShow) return "";
  const meta = nodeMeta[node.type] || { label: node.id };
  const brief = nodeBriefModelV2(node);
  const batchLines =
    node.id === "output" && generatedVideos.length
      ? generatedVideos.map((item, itemIndex) => {
          const summary = [item.duration ? `${item.duration}s` : "", item.aspect].filter(Boolean).join(" / ");
          return `${itemIndex + 1}. ${item.title}${summary ? ` (${summary})` : ""}`;
        })
      : history.slice(-4).map((item) => `V${item.batchIndex}: ${item.summary}`);
  const chips = [...asList(brief.chips)];
  if (history.length > 1 && node.id !== "output") {
    chips.push(`批次 ${history.length}`);
  }
  if (node.id === "output" && (generatedVideos.length || batchRunState?.total)) {
    const total = batchRunState?.total || targetVideoCount();
    chips.push(`成片 ${generatedVideos.length}/${total}`);
  }
  if (issue?.chip) {
    chips.unshift(issue.chip);
  }
  const metrics = renderBriefMetrics([...observationMetrics(node), ...asList(brief.metrics)]);
  const lines = [issue?.message, ...observationLines(node), ...batchLines, ...asList(brief.lines)]
    .filter(Boolean)
    .slice(0, node.id === "output" ? 14 : 10);
  const expanded = expandedBriefNodeIds.has(node.id);
  const reviewLabel = reviewCardLabel(node);
  return `
    <article class="node-brief-card ${statusClass(node.status)} ${issue ? issue.level : ""} ${expanded ? "expanded" : ""}">
      <header class="node-brief-head">
        <span class="node-brief-index">${String(index + 1).padStart(2, "0")}</span>
        <div class="node-brief-title-wrap">
          <strong>${escapeHtml(meta.label)}</strong>
          <small>${escapeHtml(statusLabel(node.status))}</small>
        </div>
        <div class="node-brief-actions">
          <span class="node-brief-type-tag">${escapeHtml(reviewLabel)}</span>
          <button type="button" class="node-brief-locate" data-focus-brief-node="${escapeHtml(node.id)}">定位</button>
        </div>
        <button type="button" class="node-brief-toggle" data-toggle-brief-node="${escapeHtml(node.id)}">${expanded ? "收起" : "展开"}</button>
      </header>
      <h3 class="node-brief-title">${escapeHtml(brief.title || meta.label)}</h3>
      ${renderBriefChips(chips)}
      <div class="node-brief-body">
        ${metrics}
        ${renderBriefLines(lines, { clamp: node.id === "output" ? 6 : 8, maxLength: node.id === "output" ? 360 : 520 })}
        ${renderBriefArtifacts(node)}
        ${renderBriefImages(brief.images)}
        ${expanded ? `<div class="node-review-detail">${renderNodeReviewDetail(node)}</div>` : ""}
      </div>
    </article>
  `;
}

function renderNodeBriefGrid() {
  if (!els.nodeBriefGrid) return;
  const cards = orderedNodes()
    .map((node, index) => renderNodeBriefCard(node, index))
    .filter(Boolean)
    .join("");
  if (!cards) {
    els.nodeBriefGrid.innerHTML = `<div class="node-brief-empty">步骤完成后，这里会展示每一步的主要内容。</div>`;
    return;
  }
  els.nodeBriefGrid.innerHTML = cards;
}

function formatOutput(output) {
  if (!output) return "等待该步骤处理。";
  return JSON.stringify(output, null, 2);
}

function addLog(title, detail) {
  const now = new Date();
  const item = document.createElement("div");
  item.className = "run-log-item";
  item.innerHTML = `
    <span class="run-time">${now.toLocaleTimeString("zh-CN", { hour12: false })}</span>
    <div><strong>${escapeHtml(title)}</strong><br>${escapeHtml(detail)}</div>
  `;
  els.runLog.prepend(item);
}

function resetRuntime({ keepLog = false, detachTask = true } = {}) {
  if (detachTask) {
    clearTaskPolling();
    activeTask = null;
    activeTaskId = null;
    lastTaskSignature = "";
    isRunning = false;
  }
  workflow.nodes.forEach((node) => {
    node.status = "idle";
    node.progress = 0;
    node.output = null;
  });
  workflow.connections.forEach((connection) => {
    connection.status = "idle";
  });
  if (!keepLog) {
    els.runLog.innerHTML = "";
    els.runTitle.textContent = "尚未运行";
  }
  render();
}

async function clearCurrentWorkflow() {
  const taskId = activeTaskId || activeTask?.task_id || "";
  if (taskId && getAccessToken()) {
    try {
      const result = await apiRequest(`/tasks/${encodeURIComponent(taskId)}/clear`, {
        method: "POST",
        body: JSON.stringify({ clear_files: true }),
      });
      const removedCount = Array.isArray(result?.removed_files) ? result.removed_files.length : 0;
      if (result?.task) {
        rememberTask(result.task);
      }
      addLog("清空状态", removedCount ? `已取消任务并清理 ${removedCount} 个本地生成文件。` : "已取消任务并清空当前状态。");
    } catch (error) {
      addLog("清空状态", error.message || "取消任务失败，已清空本地画布状态。");
    }
  }
  downloadedTaskId = "";
  resetRuntime();
}

function setNodeStatus(id, status, progress) {
  const node = findNode(id);
  if (!node) return;
  node.status = status;
  node.progress = progress;
  render();
}

function setIncomingConnections(id, status) {
  workflow.connections.forEach((connection) => {
    if (connection.to === id) connection.status = status;
  });
  renderLinks();
}

function setOutgoingConnections(id, status) {
  workflow.connections.forEach((connection) => {
    if (connection.from === id) connection.status = status;
  });
  renderLinks();
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function runWorkflow() {
  if (isRunning) return;
  if (!getAccessToken()) {
    addLog("登录提示", "请先登录主站账号，再开始视频制作。");
    return;
  }
  await refreshProviderStatus({ silent: true });

  const inputNode = findNode("input");
  const title = String(inputNode?.fields.topic || "").trim();
  if (!title) {
    selectedId = "input";
    addLog("需要主题", "请先在“内容输入”步骤填写视频主题，再开始制作。");
    render();
    return;
  }

  runToken += 1;
  activeTask = null;
  activeTaskId = null;
  downloadedTaskId = "";
  clearTaskPolling();
  lastTaskSignature = "";
  resetRuntime({ keepLog: true, detachTask: false });
  isRunning = true;
  els.runLog.innerHTML = "";
  els.runTitle.textContent = "正在创建制作任务";
  addLog("开始", "准备把当前制作内容交给站内服务逐步处理。");

  const payload = {
    title,
    horse_name: inputNode?.fields.horse || "",
    duration: Number(inputNode?.fields.duration || 30),
    aspect_ratio: inputNode?.fields.aspect || "9:16",
    workflow_definition: getWorkflowDefinition(),
    input_payload: buildWorkflowInputPayload(),
    auto_start: true,
  };

  try {
    const result = await apiRequest("/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const task = result?.task;
    if (!task) {
      throw new Error("站内服务没有返回制作任务。");
    }

    rememberTask(task);
    addLog("任务创建", `${task.task_id} 已创建`);
    if (result.message) {
      addLog("制作流程", result.message);
    }
    applyTaskSnapshot(task);
    logTaskUpdate(task, true);

    if (result.dispatch_status === "queued" || ["queued", "processing"].includes(task.status)) {
      startTaskPolling(task.task_id);
    } else {
      isRunning = false;
      render();
    }
  } catch (error) {
    isRunning = false;
    els.runTitle.textContent = "创建失败";
    addLog("创建失败", error.message || "无法创建制作任务。");
    render();
  }
}

function stopWorkflow() {
  clearTaskPolling();
  isRunning = false;
  addLog("停止", activeTaskId ? `已停止本地刷新，任务 ${activeTaskId} 仍可继续处理。` : "当前没有正在刷新的任务。");
  render();
}

function buildMockOutput(id) {
  const input = findNode("input").fields;
  const script = findNode("script").output;
  const storyboard = findNode("storyboard").output;
  const keyframe = findNode("keyframe").output;
  const shotCount = Number(findNode("storyboard").fields.shotCount || 5);
  if (id === "input") {
    return {
      topic: input.topic,
      horse: input.horse,
      duration: Number(input.duration),
      aspect: input.aspect,
      brief: input.brief,
    };
  }
  if (id === "script") {
    return {
      title: input.topic,
      voiceover: `${input.horse}不是一匹普通坐骑，它把速度、忠义和战场上的命运感凝成一个名字。`,
      scriptStyle: findNode("script").fields.style,
      scenesExpected: shotCount,
      model: findNode("script").fields.model,
    };
  }
  if (id === "storyboard") {
    return {
      shots: Array.from({ length: shotCount }).map((_, index) => ({
        scene: index + 1,
        seconds: Number(findNode("storyboard").fields.shotSeconds || 6),
        camera: ["低角度登场", "战场横移", "人物并肩", "高速冲锋", "片尾定格"][index % 5],
        prompt: `${input.horse}，国风史诗电影感，第 ${index + 1} 镜，${findNode("storyboard").fields.camera}`,
      })),
    };
  }
  if (id === "keyframe") {
    return {
      provider: findNode("keyframe").fields.provider,
      referenceMode: findNode("keyframe").fields.referenceMode,
      images: (storyboard?.shots || []).map((shot) => ({
        scene: shot.scene,
        prompt: `${shot.prompt}，${findNode("keyframe").fields.consistency}`,
        imageUrl: `mock://keyframes/${input.horse}_${shot.scene}.png`,
      })),
    };
  }
  if (id === "veo") {
    const soundscape = findNode("voice").fields.soundscape || "马蹄声、战场风声、低沉鼓点、电影感环境声";
    const subtitleStyle = findNode("subtitle").fields.style || "金色下三分之一";
    return {
      provider: findNode("veo").fields.provider,
      modelTarget: findNode("veo").fields.model,
      generateAudio: findNode("veo").fields.generateAudio === "是",
      audioPrompt: `生成电影感音频：${soundscape}。中文普通话口语旁白优先，禁止英文和无声片段。`,
      subtitlePrompt: `如片段支持内嵌字幕，使用${subtitleStyle}简体中文字幕；站内 SRT 作为备用。`,
      clips: (storyboard?.shots || []).map((shot) => ({
        scene: shot.scene,
        operation: `veo_operation_${String(shot.scene).padStart(2, "0")}`,
        url: `mock://veo/clips/${input.horse}_${shot.scene}.mp4`,
        prompt: `${shot.prompt}，包含同步马蹄声、环境声和字幕意图。`,
        referenceImage: keyframe?.images?.find((image) => image.scene === shot.scene)?.imageUrl || null,
      })),
    };
  }
  if (id === "voice") {
    return {
      text: script?.voiceover || "",
      mode: findNode("voice").fields.mode,
      engine: findNode("voice").fields.engine,
      voice: findNode("voice").fields.voice,
      soundscape: findNode("voice").fields.soundscape,
      audioUrl: null,
      duration: Number(input.duration),
      fallback: "优先使用中文配音；未配置独立配音时使用片段原生声音提示。",
    };
  }
  if (id === "subtitle") {
    return {
      mode: findNode("subtitle").fields.mode,
      style: findNode("subtitle").fields.style,
      srtUrl: "mock://subtitle/storyboard.srt",
      segments: (storyboard?.shots || []).map((shot, index) => ({
        start: index * Number(findNode("storyboard").fields.shotSeconds || 6),
        end: (index + 1) * Number(findNode("storyboard").fields.shotSeconds || 6),
        text: `${input.horse}，第 ${shot.scene} 幕：${shot.camera}`,
      })),
    };
  }
  if (id === "compose") {
    return {
      engine: findNode("compose").fields.engine,
      transition: findNode("compose").fields.transition,
      videoUrl: "mock://final/video-factory-preview.mp4",
      thumbnailUrl: horseImages[input.horse] || horseImages["赤兔"],
      audioMix: findNode("compose").fields.ducking,
    };
  }
  return {
    taskId: `vid_preview_${Date.now().toString(36)}`,
    status: "completed",
    videoUrl: "mock://final/video-factory-preview.mp4",
    callback: findNode("output").fields.callback,
    executionMode: "site-workflow",
  };
}

function getCompletionText(id) {
  return {
    input: "内容、时长、画幅已进入 payload。",
    script: "脚本标题、旁白和结构化要求已生成。",
    storyboard: "分镜画面描述已拆分为多个镜头。",
    keyframe: "关键帧画面描述和参考图任务已生成。",
    veo: "视频片段已返回任务信息和片段地址。",
    voice: "中文口语配音规划已写入；配置独立配音后会合成普通话音轨。",
    subtitle: "字幕内容已写入片段要求，站内 SRT 作为备用。",
    compose: "合成视频、封面和混音结果已生成。",
    output: "任务完成，后续会把占位结果替换为真实成片输出。",
  }[id];
}

function getWorkflowDefinition() {
  return {
    name: "baiqipu-video-factory-site-workflow",
    mode: "site-workflow",
    orchestration: {
      engine: "baiqipu-backend",
      runEndpoint: "/api/v1/video/workflow/tasks/{task_id}/run",
      secrets: "store-in-backend-env",
    },
    nodes: workflow.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      label: nodeMeta[node.type]?.label || node.id,
      position: { x: node.x, y: node.y },
      parameters: node.fields,
    })),
    connections: workflow.connections.map(({ id, from, to }) => ({ id, from, to })),
  };
}

function resetLayout() {
  const fresh = clone(defaultWorkflow);
  autoFitZoom = true;
  workflow.nodes.forEach((node) => {
    const next = fresh.nodes.find((item) => item.id === node.id);
    if (next) {
      node.x = next.x;
      node.y = next.y;
    }
  });
  addLog("布局", "步骤位置已恢复为默认制作布局。");
  render();
}

function fieldDefinitionFor(nodeId, key) {
  const node = findNode(nodeId);
  if (!node) return null;
  return (fieldDefs[node.type] || []).find((field) => field.key === key) || null;
}

function isModelSelectionField(nodeId, key) {
  return Boolean(fieldDefinitionFor(nodeId, key)?.modelSource);
}

function updateField(nodeId, key, value) {
  const node = findNode(nodeId);
  if (!node) return;
  const previousValue = node.fields[key];
  node.fields[key] = value;
  if (isModelSelectionField(nodeId, key) && String(previousValue ?? "") !== String(value ?? "")) {
    node.fields.__modelLocked = "1";
    addLog("模型选择", `${nodeMeta[node.type]?.label || nodeId} 已切换为 ${value}。`);
  }
  if (nodeId === "input" && key === "runMode") {
    applyRunModePreset(value, { silent: true });
  }
  if (node.status !== "idle") {
    node.status = "idle";
    node.progress = 0;
    node.output = null;
  }
  renderNodes();
  renderLinks();
  renderPreview();
  renderStats();
}

function updateFieldQuietly(nodeId, key, value) {
  const node = findNode(nodeId);
  if (!node) return;
  node.fields[key] = value;
  if (isModelSelectionField(nodeId, key)) {
    node.fields.__modelLocked = "1";
  }
  if (nodeId === "input" && key === "runMode") {
    applyRunModePreset(value);
  }
  if (node.status !== "idle") {
    node.status = "idle";
    node.progress = 0;
    node.output = null;
  }
  renderInspector();
  renderPreview();
  renderStats();
}

function pickUploadValue(container, keys) {
  if (!container || typeof container !== "object") return "";
  for (const key of keys) {
    const value = container[key];
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      return value;
    }
  }
  return "";
}

function inferReferenceMediaType(file) {
  const mime = String(file?.type || "").toLowerCase();
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  const name = String(file?.name || "").toLowerCase();
  if (/\.(png|jpg|jpeg|webp|gif|bmp|avif)$/i.test(name)) return "image";
  if (/\.(mp4|mov|m4v|webm|avi|mkv)$/i.test(name)) return "video";
  return "unknown";
}

function parseReferenceAssets(rawAssets) {
  if (Array.isArray(rawAssets)) return rawAssets.filter(Boolean);
  if (typeof rawAssets === "string" && rawAssets.trim()) {
    try {
      const parsed = JSON.parse(rawAssets);
      return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch {
      return [];
    }
  }
  return [];
}

function referenceAssetsFromFields(fields = {}) {
  const assets = parseReferenceAssets(fields.assets);
  if (assets.length) return assets;
  const mediaUrl = String(fields.mediaUrl || "").trim();
  const localPath = String(fields.localPath || "").trim();
  if (!mediaUrl && !localPath) return [];
  return [
    {
      id: "legacy-reference",
      name: compactText(localPath || mediaUrl, 48),
      mediaType: fields.mediaType || "unknown",
      mediaUrl,
      localPath,
      sourceType: fields.sourceType || "上传文件",
    },
  ];
}

function referenceWeightsFromFields(fields = {}) {
  const subject = Math.max(0, Number(fields.subjectWeight || 60) || 60);
  const style = Math.max(0, Number(fields.styleWeight || 25) || 25);
  const camera = Math.max(0, Number(fields.cameraWeight || 15) || 15);
  const total = subject + style + camera || 100;
  return {
    subject,
    style,
    camera,
    total,
    normalized: {
      subject: Math.round((subject / total) * 100),
      style: Math.round((style / total) * 100),
      camera: Math.round((camera / total) * 100),
    },
  };
}

function makeReferenceAssetId(asset = {}) {
  return [
    asset.mediaUrl,
    asset.localPath,
    asset.name,
    Date.now(),
    Math.random().toString(16).slice(2, 7),
  ]
    .filter(Boolean)
    .join("-")
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .slice(0, 90);
}

function saveReferenceAssets(node, assets) {
  if (!node) return;
  const safeAssets = asList(assets).slice(0, 12);
  node.fields.assets = safeAssets;
  const latest = safeAssets[safeAssets.length - 1];
  if (latest) {
    node.fields.sourceType = latest.sourceType || node.fields.sourceType || "上传文件";
    node.fields.mediaType = latest.mediaType || node.fields.mediaType || "unknown";
    node.fields.mediaUrl = latest.mediaUrl || node.fields.mediaUrl || "";
    node.fields.localPath = latest.localPath || node.fields.localPath || "";
  }
}

function appendReferenceAsset(node, asset) {
  if (!node || !asset) return;
  const assets = referenceAssetsFromFields(node.fields);
  const assetId = asset.id || makeReferenceAssetId(asset);
  const nextAsset = { ...asset, id: assetId };
  const deduped = assets.filter((item) => {
    const sameUrl = item.mediaUrl && nextAsset.mediaUrl && item.mediaUrl === nextAsset.mediaUrl;
    const samePath = item.localPath && nextAsset.localPath && item.localPath === nextAsset.localPath;
    return !sameUrl && !samePath && item.id !== assetId;
  });
  saveReferenceAssets(node, [...deduped, nextAsset]);
}

function removeReferenceAsset(assetId) {
  const node = findNode("reference_input");
  if (!node) return;
  const nextAssets = referenceAssetsFromFields(node.fields).filter((asset) => String(asset.id) !== String(assetId));
  saveReferenceAssets(node, nextAssets);
  if (!nextAssets.length) {
    node.fields.mediaUrl = "";
    node.fields.localPath = "";
    node.fields.mediaType = "unknown";
  }
  addLog("参考素材", "已移除一个参考素材。");
  render();
}

function referenceKeywordList() {
  const output = findNode("reference_analyze")?.output || {};
  return [
    output.visualStyle,
    output.cameraLanguage,
    output.lighting,
    output.motion,
    output.color,
    output.rhythm,
  ]
    .map((item) => compactText(item, 28))
    .filter(Boolean)
    .slice(0, 8);
}

function renderReferenceWeightBars(fields = {}) {
  const weights = referenceWeightsFromFields(fields);
  const items = [
    ["主体", weights.normalized.subject, "subject"],
    ["风格", weights.normalized.style, "style"],
    ["镜头", weights.normalized.camera, "camera"],
  ];
  return `
    <div class="reference-weight-panel">
      ${items.map(([label, value, key]) => `
        <div class="reference-weight-item ${key}">
          <span>${label}</span>
          <strong>${value}%</strong>
          <i><b style="width:${value}%"></b></i>
        </div>
      `).join("")}
    </div>
  `;
}

function renderReferenceAssetPreview(asset) {
  const url = safeMediaUrl(asset.mediaUrl || asset.previewUrl || asset.frameUrl);
  if (asset.mediaType === "image" && url) {
    return `<img src="${escapeHtml(url)}" alt="${escapeHtml(asset.name || "reference")}" loading="lazy" />`;
  }
  if (asset.mediaType === "video" && url) {
    return `<video src="${escapeHtml(url)}" muted playsinline preload="metadata"></video>`;
  }
  return `<span class="reference-asset-fallback">${escapeHtml((asset.mediaType || "素材").slice(0, 8))}</span>`;
}

function referenceAssetRoleLabel(asset, index = 0) {
  if (asset?.role) return String(asset.role);
  return ["主体参考", "风格参考", "镜头参考"][Number(index) % 3] || "参考素材";
}

function renderReferenceVisualPanel(node) {
  const assets = referenceAssetsFromFields(node.fields);
  const keywords = referenceKeywordList();
  const frameUrl = safeMediaUrl(findNode("reference_analyze")?.output?.source?.frameUrl);
  return `
    <div class="reference-visual-panel">
      ${renderReferenceWeightBars(node.fields)}
      <div class="reference-assets-head">
        <strong>参考素材</strong>
        <span>${assets.length ? `${assets.length} 个素材` : "尚未添加"}</span>
      </div>
      ${assets.length ? `
        <div class="reference-asset-grid">
          ${assets.map((asset, index) => `
            <figure class="reference-asset-card">
              <div class="reference-asset-media">${renderReferenceAssetPreview(asset)}</div>
              <div class="reference-asset-badges">
                <span>${escapeHtml(referenceAssetRoleLabel(asset, index))}</span>
                <span>${escapeHtml(asset.mediaType === "video" ? "视频" : asset.mediaType === "image" ? "图片" : "素材")}</span>
              </div>
              <figcaption>
                <strong>${escapeHtml(compactText(asset.name || `素材 ${index + 1}`, 26))}</strong>
                <span>${escapeHtml(asset.mediaType || "unknown")} / ${escapeHtml(asset.sourceType || "上传文件")}</span>
              </figcaption>
              <button type="button" data-remove-reference-asset="${escapeHtml(asset.id)}">删除</button>
            </figure>
          `).join("")}
        </div>
      ` : `<div class="reference-assets-empty">上传图片或视频后，这里会显示缩略图和参考权重。</div>`}
      ${frameUrl ? `
        <div class="reference-frame-strip">
          <span>视频抽帧</span>
          <img src="${escapeHtml(frameUrl)}" alt="reference frame" loading="lazy" />
        </div>
      ` : ""}
      ${keywords.length ? `
        <div class="reference-keywords">
          <span>识别关键词</span>
          <div>${keywords.map((keyword) => `<b>${escapeHtml(keyword)}</b>`).join("")}</div>
        </div>
      ` : ""}
    </div>
  `;
}

function applyReferenceUploadResult(payload) {
  const node = findNode("reference_input");
  if (!node || !payload || typeof payload !== "object") return;
  const payloadData = payload.data && typeof payload.data === "object" ? payload.data : payload;
  const mediaTypeValue =
    pickUploadValue(payloadData, ["mediaType", "media_type"]) ||
    pickUploadValue(payload, ["mediaType", "media_type"]);
  const mediaUrlValue =
    pickUploadValue(payloadData, ["mediaUrl", "media_url", "url", "fileUrl", "file_url"]) ||
    pickUploadValue(payload, ["mediaUrl", "media_url", "url", "fileUrl", "file_url"]);
  const localPathValue =
    pickUploadValue(payloadData, ["localPath", "local_path", "path"]) ||
    pickUploadValue(payload, ["localPath", "local_path", "path"]);
  const fileNameValue =
    pickUploadValue(payloadData, ["fileName", "file_name", "name", "originalName"]) ||
    pickUploadValue(payload, ["fileName", "file_name", "name", "originalName"]) ||
    localPathValue ||
    mediaUrlValue ||
    "reference";

  node.fields.sourceType = "上传文件";
  if (mediaTypeValue) {
    node.fields.mediaType = String(mediaTypeValue);
  } else if (!node.fields.mediaType) {
    node.fields.mediaType = "unknown";
  }
  if (mediaUrlValue) node.fields.mediaUrl = String(mediaUrlValue);
  if (localPathValue) node.fields.localPath = String(localPathValue);
  appendReferenceAsset(node, {
    name: String(fileNameValue),
    mediaType: String(mediaTypeValue || node.fields.mediaType || "unknown"),
    mediaUrl: mediaUrlValue ? String(mediaUrlValue) : "",
    localPath: localPathValue ? String(localPathValue) : "",
    sourceType: "上传文件",
    createdAt: new Date().toISOString(),
  });
}

function applyReferenceUploadLocalFallback(file, reason = "") {
  const node = findNode("reference_input");
  if (!node) return;
  const inferredType = inferReferenceMediaType(file);
  node.fields.sourceType = "上传文件";
  node.fields.mediaType = inferredType || node.fields.mediaType || "unknown";
  node.fields.localPath = `[local] ${String(file?.name || "reference")}`;
  node.fields.mediaUrl = String(node.fields.mediaUrl || "");
  appendReferenceAsset(node, {
    name: String(file?.name || "reference"),
    mediaType: inferredType || "unknown",
    mediaUrl: "",
    localPath: node.fields.localPath,
    sourceType: "本地选择",
    previewUrl: file ? URL.createObjectURL(file) : "",
    createdAt: new Date().toISOString(),
  });
  if (reason) {
    node.fields.note = `上传服务不可用：${reason}`;
  }
}

async function uploadReferenceFiles(files) {
  for (const file of Array.from(files || [])) {
    await uploadReferenceFile(file);
  }
}

async function uploadReferenceFile(file) {
  if (!file) return;
  if (!getAccessToken()) {
    addLog("参考素材", "请先登录后再上传参考素材。");
    return;
  }
  const formData = new FormData();
  formData.append("file", file, file.name || "reference");
  addLog("参考素材", `正在上传：${file.name || "reference"}`);
  try {
    const payload = await apiRequest("/reference/upload", {
      method: "POST",
      body: formData,
    });
    applyReferenceUploadResult(payload);
    if (!String(findNode("reference_input")?.fields?.mediaUrl || "").trim()) {
      applyReferenceUploadLocalFallback(file);
    }
    addLog("参考素材", payload?.message || "上传成功，已写入参考步骤。");
    selectedId = "reference_input";
    render();
  } catch (error) {
    const message = String(error?.message || "上传失败，请检查登录态和文件格式。");
    const isUploadEndpointMissing = Number(error?.status || 0) === 404 || /not found/i.test(message);
    applyReferenceUploadLocalFallback(file, isUploadEndpointMissing ? "站内缺少 /reference/upload 路由" : "");
    if (isUploadEndpointMissing) {
      addLog("参考素材", "站内未启用上传服务，已保留本地素材选择。请补齐 /api/v1/video/workflow/reference/upload。");
    } else {
      addLog("参考素材", message);
    }
    selectedId = "reference_input";
    render();
  }
}

function bindEvents() {
  const loginLink = document.querySelector(".login-link");
  if (loginLink) {
    loginLink.addEventListener("click", (event) => {
      if (isAuthenticated()) {
        event.preventDefault();
      }
    });
  }
  window.addEventListener("storage", (event) => {
    if (!event.key || event.key === AUTH_STORAGE_KEY) {
      renderAuthLink();
    }
  });
  window.addEventListener("pageshow", renderAuthLink);

  if (els.taskList) {
    els.taskList.addEventListener("click", (event) => {
      const deleteButton = event.target.closest("[data-delete-task-id]");
      if (deleteButton) {
        event.preventDefault();
        event.stopPropagation();
        deleteTaskHistory(deleteButton.dataset.deleteTaskId);
        return;
      }
      const downloadLink = event.target.closest(".task-download-link");
      if (downloadLink) {
        event.preventDefault();
        event.stopPropagation();
        const taskIdFromData = downloadLink.getAttribute("data-download-task-id");
        const cardTaskId = downloadLink.closest(".task-card")?.querySelector("[data-task-id]")?.dataset?.taskId;
        const taskId = taskIdFromData || cardTaskId || "";
        if (taskId) {
          void downloadTaskVideoById(taskId);
        }
        return;
      }
      const button = event.target.closest("[data-task-id]");
      if (!button) return;
      selectTask(button.dataset.taskId);
    });
  }

  if (els.generatedVideoMenu) {
    els.generatedVideoMenu.addEventListener("click", (event) => {
      const refreshButton = event.target.closest("[data-refresh-generated-library]");
      if (refreshButton) {
        renderGeneratedVideoMenu();
        renderPreview();
        return;
      }
      const deleteButton = event.target.closest("[data-delete-generated-task]");
      if (deleteButton) {
        const taskId = deleteButton.getAttribute("data-delete-generated-task") || "";
        if (taskId) {
          void deleteTaskHistory(taskId);
        }
        return;
      }
      const reuseButton = event.target.closest("[data-reuse-generated-task]");
      if (reuseButton) {
        const taskId = reuseButton.getAttribute("data-reuse-generated-task") || "";
        if (taskId) {
          void reuseGeneratedTaskConfig(taskId);
        }
        return;
      }
      const selectButton = event.target.closest("[data-select-generated-task]");
      if (selectButton) {
        selectedGeneratedTaskId = selectButton.getAttribute("data-select-generated-task") || "";
        renderGeneratedVideoMenu();
        renderPreview();
        renderDownloadButton();
        return;
      }
      const downloadButton = event.target.closest("[data-download-task-id]");
      if (downloadButton) {
        const taskId = downloadButton.getAttribute("data-download-task-id") || "";
        if (taskId) {
          void downloadTaskVideoById(taskId);
        }
      }
    });
  }

  document.addEventListener("click", (event) => {
    const diagnosticButton = event.target.closest("[data-error-node]");
    if (!diagnosticButton) return;
    const nodeId = diagnosticButton.getAttribute("data-error-node") || "";
    if (!nodeId || !findNode(nodeId)) return;
    focusCanvasNode(nodeId);
  });

  els.presetPanel?.addEventListener("click", (event) => {
    const presetButton = event.target.closest("[data-preset-id]");
    if (presetButton) {
      applyParameterPreset(presetButton.getAttribute("data-preset-id") || "");
      return;
    }
    const applyButton = event.target.closest("[data-apply-selected-preset]");
    if (!applyButton) return;
    const presetSelect = els.presetPanel.querySelector("#presetSelect");
    applyParameterPreset(presetSelect?.value || selectedPresetId || PARAMETER_PRESETS[0]?.id || "");
  });

  els.presetPanel?.addEventListener("change", (event) => {
    const presetSelect = event.target.closest("#presetSelect");
    if (!presetSelect) return;
    selectedPresetId = presetSelect.value || selectedPresetId;
    renderPresetPanel();
  });

  els.batchQueue?.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-batch-skip-toggle]");
    if (!toggle) return;
    batchQueueOptions.skipFailed = !batchQueueOptions.skipFailed;
    if (batchRunState) {
      batchRunState.skipFailed = batchQueueOptions.skipFailed;
    }
    addLog("批量队列", batchQueueOptions.skipFailed ? "失败后将跳过并继续下一条。" : "失败后将暂停，便于排查。");
    renderBatchQueue();
  });

  if (els.executionTimeline) {
    els.executionTimeline.addEventListener("click", (event) => {
      const button = event.target.closest("[data-select-node]");
      if (!button) return;
      focusCanvasNode(button.dataset.selectNode);
    });
  }

  els.nodeBriefGrid?.addEventListener("click", (event) => {
    const focusButton = event.target.closest("[data-focus-brief-node]");
    if (focusButton) {
      focusCanvasNode(focusButton.getAttribute("data-focus-brief-node") || "");
      return;
    }
    const toggle = event.target.closest("[data-toggle-brief-node]");
    if (!toggle) return;
    const nodeId = toggle.getAttribute("data-toggle-brief-node") || "";
    if (expandedBriefNodeIds.has(nodeId)) {
      expandedBriefNodeIds.delete(nodeId);
    } else {
      expandedBriefNodeIds.add(nodeId);
    }
    renderNodeBriefGrid();
  });

  els.nodeList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-select-node]");
    if (!button) return;
    focusCanvasNode(button.dataset.selectNode);
  });

  els.nodesLayer.addEventListener("click", (event) => {
    const nodeEl = event.target.closest("[data-node-id]");
    if (!nodeEl) return;
    selectedId = nodeEl.dataset.nodeId;
    render();
  });

  els.nodesLayer.addEventListener("input", (event) => {
    const target = event.target;
    if (!target.matches("[data-node-field]")) return;
    updateFieldQuietly(target.dataset.nodeId, target.dataset.nodeField, target.value);
  });

  els.inspectorContent.addEventListener("input", (event) => {
    const target = event.target;
    if (!target.matches("[data-field]")) return;
    updateField(selectedId, target.dataset.field, target.value);
  });

  els.inspectorContent.addEventListener("change", (event) => {
    const target = event.target;
    if (!target.matches("[data-field]")) return;
    updateField(selectedId, target.dataset.field, target.value);
    renderInspector();
  });

  els.inspectorContent.addEventListener("click", (event) => {
    const xhsTest = event.target.closest("[data-xhs-test]");
    if (xhsTest) {
      void testXhsConnection();
      return;
    }
    const refreshModels = event.target.closest("[data-refresh-provider-models]");
    if (refreshModels) {
      void refreshProviderModels({ silent: false });
      return;
    }
    const removeReference = event.target.closest("[data-remove-reference-asset]");
    if (removeReference) {
      removeReferenceAsset(removeReference.getAttribute("data-remove-reference-asset") || "");
      return;
    }
    const trigger = event.target.closest("[data-reference-upload-trigger]");
    if (!trigger) return;
    const input = els.inspectorContent.querySelector("[data-reference-upload-input]");
    input?.click();
  });

  els.inspectorContent.addEventListener("change", (event) => {
    const target = event.target;
    if (!target.matches("[data-reference-upload-input]")) return;
    const files = Array.from(target.files || []);
    if (files.length) {
      void uploadReferenceFiles(files);
    }
    target.value = "";
  });

  document.querySelector("#runBtn").addEventListener("click", runWorkflow);
  document.querySelector("#downloadVideoBtn")?.addEventListener("click", downloadCurrentTaskVideo);
  document.querySelector("#stopBtn").addEventListener("click", stopWorkflow);
  document.querySelector("#resetBtn").addEventListener("click", clearCurrentWorkflow);
  document.querySelector("#saveBtn").addEventListener("click", saveWorkflow);
  document.querySelector("#layoutBtn").addEventListener("click", resetLayout);
  document.querySelector("#refreshTasksBtn").addEventListener("click", refreshTaskList);
  document.querySelector("#retryTaskBtn").addEventListener("click", retryActiveTask);
  els.clearTaskHistoryBtn?.addEventListener("click", clearTaskHistory);
  document.querySelector("#exportBtn").addEventListener("click", () => {
    els.jsonExport.value = JSON.stringify(getWorkflowDefinition(), null, 2);
    els.jsonDialog.showModal();
  });
  document.querySelector("#closeJsonBtn").addEventListener("click", () => els.jsonDialog.close());
  document.querySelector("#zoomInBtn").addEventListener("click", () => {
    autoFitZoom = false;
    zoom = Math.min(1.25, zoom + 0.1);
    render();
  });
  document.querySelector("#zoomOutBtn").addEventListener("click", () => {
    autoFitZoom = false;
    zoom = Math.max(0.7, zoom - 0.1);
    render();
  });
  window.addEventListener("resize", () => {
    if (autoFitZoom) {
      render();
    }
  });

  bindCanvasPan();
  bindDrag();
}

function bindCanvasPan() {
  let panState = null;

  const endPan = () => {
    panState = null;
    els.canvasViewport.classList.remove("panning");
  };

  els.canvasViewport.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    if (
      event.target.closest(
        "[data-node-id], [data-drag-node], textarea, input, select, button, a, .task-download-link, .icon-button"
      )
    ) {
      return;
    }
    autoFitZoom = false;
    panState = {
      pointerId: event.pointerId,
      lastX: event.clientX,
      lastY: event.clientY,
    };
    els.canvasViewport.classList.add("panning");
    els.canvasViewport.setPointerCapture?.(event.pointerId);
  });

  els.canvasViewport.addEventListener("pointermove", (event) => {
    if (!panState || panState.pointerId !== event.pointerId) return;
    event.preventDefault();
    const deltaX = event.clientX - panState.lastX;
    const deltaY = event.clientY - panState.lastY;
    panState.lastX = event.clientX;
    panState.lastY = event.clientY;
    panX += deltaX;
    panY += deltaY;
    applyCanvasZoom();
    renderCanvasMinimap();
  });

  els.canvasViewport.addEventListener("pointerup", endPan);
  els.canvasViewport.addEventListener("pointercancel", endPan);
  els.canvasViewport.addEventListener("pointerleave", (event) => {
    if (!panState) return;
    if (event.buttons === 0) {
      endPan();
    }
  });
}

function bindDrag() {
  let dragState = null;
  let dragFrame = 0;

  function paintDraggedNode() {
    dragFrame = 0;
    if (!dragState) return;
    const node = findNode(dragState.id);
    const nodeEl = document.querySelector(`[data-node-id="${dragState.id}"]`);
    if (!node || !nodeEl) return;
    nodeEl.style.transform = `translate(${node.x}px, ${node.y}px)`;
    renderLinks();
    renderCanvasMinimap();
  }

  els.nodesLayer.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest("[data-drag-node]");
    if (!handle) return;
    const node = findNode(handle.dataset.dragNode);
    if (!node) return;
    selectedId = node.id;
    dragState = {
      id: node.id,
      lastX: event.clientX,
      lastY: event.clientY,
    };
    handle.setPointerCapture(event.pointerId);
    const nodeEl = handle.closest("[data-node-id]");
    if (nodeEl) {
      nodeEl.classList.add("dragging", "selected");
    }
    renderNodeList();
    renderInspector();
    renderPreview();
  });

  els.nodesLayer.addEventListener("pointermove", (event) => {
    if (!dragState) return;
    const node = findNode(dragState.id);
    if (!node) return;
    event.preventDefault();
    const deltaX = (event.clientX - dragState.lastX) / zoom;
    const deltaY = (event.clientY - dragState.lastY) / zoom;
    dragState.lastX = event.clientX;
    dragState.lastY = event.clientY;
    const minX = 16;
    const minY = 16;
    const maxX = CANVAS_WIDTH - NODE_WIDTH - 16;
    const maxY = CANVAS_HEIGHT - NODE_HEIGHT - 16;
    node.x = Math.max(minX, Math.min(maxX, node.x + deltaX));
    node.y = Math.max(minY, Math.min(maxY, node.y + deltaY));
    if (!dragFrame) {
      dragFrame = window.requestAnimationFrame(paintDraggedNode);
    }
  });

  window.addEventListener("pointerup", () => {
    if (!dragState) return;
    dragState = null;
    if (dragFrame) {
      window.cancelAnimationFrame(dragFrame);
      dragFrame = 0;
    }
    renderNodes();
    renderLinks();
  });

  window.addEventListener("pointercancel", () => {
    dragState = null;
    if (dragFrame) {
      window.cancelAnimationFrame(dragFrame);
      dragFrame = 0;
    }
    renderNodes();
    renderLinks();
  });
}

function batchRoundDisplay(index, total) {
  return total > 1 ? `${index}/${total}` : "1/1";
}

function batchVariantInstruction(index, total) {
  const variants = [
    "focus on dramatic opening conflict and faster rhythm",
    "focus on inner emotion and restrained narration",
    "focus on turning point and decisive action",
    "focus on reflective ending and aftertaste",
  ];
  const direction = variants[(index - 1) % variants.length];
  return `Batch ${index}/${total}. Keep same topic, but script and narration must be clearly different from other versions. ${direction}. Output Chinese spoken narration.`;
}

function buildTaskPayloadForRound(index, total) {
  const inputNode = findNode("input");
  const baseTitle = String(inputNode?.fields?.topic || "").trim();
  const inputPayload = buildWorkflowInputPayload();
  const roundHint = batchVariantInstruction(index, total);
  const scriptFields = { ...(inputPayload.script || {}) };
  const basePrompt = String(scriptFields.customPrompt || "").trim();
  scriptFields.customPrompt = [basePrompt, roundHint].filter(Boolean).join("\n\n");
  inputPayload.script = scriptFields;
  inputPayload.batch = {
    index,
    total,
    roundHint,
    seed: `${Date.now()}-${index}`,
  };
  if (total > 1) {
    inputPayload.brief = [String(inputPayload.brief || "").trim(), `Batch version ${index}/${total}`]
      .filter(Boolean)
      .join(" | ");
  }

  return {
    title: total > 1 ? `${baseTitle} #${index}` : baseTitle,
    horse_name: inputNode?.fields?.horse || "",
    duration: Number(inputNode?.fields?.duration || 30),
    aspect_ratio: inputNode?.fields?.aspect || "9:16",
    workflow_definition: getWorkflowDefinition(),
    input_payload: inputPayload,
    auto_start: true,
  };
}

function resetPipelineForNextRound(nextIndex, total) {
  const inputNode = findNode("input");
  if (inputNode) {
    inputNode.status = "done";
    inputNode.progress = 100;
  }
  NODE_SEQUENCE.forEach((nodeId) => {
    if (nodeId === "input") return;
    const node = findNode(nodeId);
    if (!node) return;
    node.status = "idle";
    node.progress = 0;
    node.output = null;
  });
  workflow.connections.forEach((connection) => {
    connection.status = "idle";
  });
  syncConnectionStates();
  addLog("批量生成", `开始第 ${batchRoundDisplay(nextIndex, total)} 条视频`);
  render();
}

function attachGeneratedVideosToOutputNode() {
  const outputNode = findNode("output");
  if (!outputNode) return;
  const current = outputNode.output && typeof outputNode.output === "object" ? outputNode.output : {};
  outputNode.output = {
    ...current,
    generatedVideos: generatedVideos.map((item) => ({
      taskId: item.taskId,
      title: item.title,
      videoUrl: item.videoUrl,
      duration: item.duration,
      aspect: item.aspect,
      batchIndex: item.batchIndex,
      batchTotal: item.batchTotal,
    })),
    batch: {
      total: batchRunState?.total || targetVideoCount(),
      completed: generatedVideos.length,
    },
  };
}

function renderPreview() {
  const input = findNode("input");
  const script = findNode("script");
  const storyboard = findNode("storyboard");
  const output = findNode("output");
  const topic = String(input?.fields?.topic || "").trim();
  const previewTask = previewTaskFromState();
  const videoUrl = getTaskVideoUrl(previewTask);
  const title = previewTask?.title || activeTask?.title || script?.output?.title || topic || "等待输入视频主题";
  const status = previewTask
    ? statusLabel(previewTask.status)
    : activeTask
      ? statusLabel(activeTask.status)
      : output.status === "done"
        ? "已生成"
        : isRunning
          ? "生成中"
          : "预览";
  const batchSummary = batchRunState
    ? `批量 ${Math.min(batchRunState.completed, batchRunState.total)}/${batchRunState.total}`
    : generatedVideos.length > 1
      ? `已生成 ${generatedVideos.length} 条`
      : "";
  const caption =
    previewTask?.result_payload?.note ||
    activeTask?.result_payload?.note ||
    activeTask?.error_message ||
    (!topic
      ? "先在内容输入步骤填写主题，系统会整理脚本与分镜。"
      : null) ||
    (output.status === "done"
      ? "当前任务已返回结果，可在上方菜单选择并下载。"
      : script?.output?.voiceover || input?.fields?.brief || "等待系统整理脚本与分镜");

  renderGeneratedVideoMenu();
  if (els.previewImage) {
    const horse = input?.fields?.horse || "赤兔";
    const image = horseImages[horse] || horseImages["赤兔"];
    if (image) {
      els.previewImage.src = image;
    }
  }
  if (els.previewVideo) {
    const frame = els.previewVideo.closest(".video-frame");
    if (videoUrl && previewTask?.status === "completed") {
      if (els.previewVideo.getAttribute("src") !== videoUrl) {
        els.previewVideo.setAttribute("src", videoUrl);
      }
      frame?.classList.add("has-video");
      els.previewEmpty?.classList.remove("show");
    } else {
      els.previewVideo.removeAttribute("src");
      els.previewVideo.load();
      frame?.classList.remove("has-video");
      els.previewEmpty?.classList.add("show");
    }
  }

  els.previewTitle.textContent = title;
  els.previewHeadline.textContent = title;
  els.previewCaption.textContent = [caption, batchSummary].filter(Boolean).join(" · ");
  els.previewAspect.textContent = input?.fields?.aspect || "9:16";
  els.previewStatus.textContent = status;
  els.previewStatus.className = `status-pill ${previewTask?.status === "completed" ? "done" : isRunning ? "running" : "waiting"}`;

  const count = Number(storyboard?.fields?.shotCount || 5);
  const activeCount = storyboard?.output?.shots?.length || 0;
  els.sceneStrip.innerHTML = Array.from({ length: Math.max(3, count) })
    .map((_, index) => {
      const shot = storyboard?.output?.shots?.[index];
      return `<div class="scene-chip ${index < activeCount ? "active" : ""}">镜头 ${index + 1}<br>${escapeHtml(shot?.camera || "等待生成")}</div>`;
    })
    .join("");
}

function startTaskPolling(taskId, options = {}) {
  clearTaskPolling();
  if (!taskId) return;
  const { onUpdate = null, onFinal = null, onError = null } = options;
  let completed = false;
  taskPollTimer = window.setInterval(async () => {
    if (completed) return;
    try {
      const task = await apiRequest(`/tasks/${taskId}`);
      rememberTask(task);
      applyTaskSnapshot(task);
      logTaskUpdate(task);
      renderTaskList();
      if (typeof onUpdate === "function") {
        onUpdate(task);
      }
      if (!["draft", "queued", "processing"].includes(task.status)) {
        completed = true;
        clearTaskPolling();
        if (typeof onFinal === "function") {
          await onFinal(task);
        }
      }
    } catch (error) {
      completed = true;
      clearTaskPolling();
      if (typeof onError === "function") {
        onError(error);
      } else {
        addLog("轮询失败", error.message || "无法更新任务状态。");
        isRunning = false;
        render();
      }
    }
  }, TASK_POLL_MS);
}

async function launchBatchRound(index, total, runId) {
  if (!batchRunState || batchRunState.stopped || runId !== runToken) return;
  batchRunState.current = index;
  batchRunState.running = true;
  renderBatchQueue();
  if (index > 1) {
    resetPipelineForNextRound(index, total);
  }

  const payload = buildTaskPayloadForRound(index, total);
  const result = await apiRequest("/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const task = result?.task;
  if (!task) {
    throw new Error("站内服务没有返回制作任务。");
  }

  rememberTask(task);
  batchRunState.taskIds = { ...(batchRunState.taskIds || {}), [index]: task.task_id };
  addLog("任务创建", `${task.task_id} (${batchRoundDisplay(index, total)})`);
  if (result.message) {
    addLog("制作流程", result.message);
  }
  applyTaskSnapshot(task);
  logTaskUpdate(task, true);
  renderTaskList();

  if (result.dispatch_status !== "queued" && !["queued", "processing"].includes(task.status)) {
    if (task.status === "completed") {
      upsertGeneratedVideoTask(task, index, total);
      rememberNodeHistory(task, index);
      attachGeneratedVideosToOutputNode();
      batchRunState.completed = index;
      selectedGeneratedTaskId = task.task_id;
      renderBatchQueue();
    }
    isRunning = false;
    batchRunState.running = false;
    render();
    return;
  }

  startTaskPolling(task.task_id, {
    onFinal: async (finalTask) => {
      if (!batchRunState || runId !== runToken) return;
      rememberTask(finalTask);
      rememberNodeHistory(finalTask, index);
      if (finalTask.status === "completed") {
        upsertGeneratedVideoTask(finalTask, index, total);
        attachGeneratedVideosToOutputNode();
        selectedGeneratedTaskId = finalTask.task_id;
        batchRunState.completed = index;
        renderBatchQueue();
        renderGeneratedVideoMenu();
        renderNodeBriefGrid();
        renderDownloadButton();
        renderPreview();
        if (index < total && !batchRunState.stopped) {
          batchRunState.nextIndex = index + 1;
          await launchBatchRound(index + 1, total, runId);
          return;
        }
        isRunning = false;
        batchRunState.running = false;
        addLog("批量生成", `已完成 ${generatedVideos.length}/${total} 条视频。`);
        render();
        return;
      }
      isRunning = false;
      batchRunState.running = false;
      batchRunState.failed = [...(batchRunState.failed || []), { index, message: finalTask.error_message || finalTask.status }];
      addLog("批量生成", `第 ${batchRoundDisplay(index, total)} 条失败：${finalTask.error_message || finalTask.status}`);
      if (batchRunState.skipFailed && index < total && !batchRunState.stopped) {
        isRunning = true;
        batchRunState.running = true;
        batchRunState.nextIndex = index + 1;
        renderBatchQueue();
        await launchBatchRound(index + 1, total, runId);
        return;
      }
      render();
    },
    onError: (error) => {
      if (runId !== runToken) return;
      isRunning = false;
      if (batchRunState) {
        batchRunState.failed = [...(batchRunState.failed || []), { index, message: error.message || "polling failed" }];
        batchRunState.running = false;
      }
      addLog("轮询失败", error.message || "无法更新任务状态。");
      if (batchRunState?.skipFailed && index < total && !batchRunState.stopped) {
        isRunning = true;
        batchRunState.running = true;
        batchRunState.nextIndex = index + 1;
        renderBatchQueue();
        void launchBatchRound(index + 1, total, runId);
        return;
      }
      render();
    },
  });
}

async function runWorkflow() {
  if (isRunning) return;
  if (!getAccessToken()) {
    addLog("登录提示", "请先登录主站账号，再开始视频制作。");
    return;
  }
  await refreshProviderStatus({ silent: true });

  const preflightChecks = buildPreflightChecks();
  const blockingIssues = preflightBlockingIssues(preflightChecks);
  renderPreflightPanel(preflightChecks);
  renderErrorCenter();
  if (blockingIssues.length) {
    const firstIssue = blockingIssues[0];
    if (firstIssue.nodeId) {
      selectedId = firstIssue.nodeId;
    }
    addLog("运行前体检", `暂不能运行：${firstIssue.title} - ${firstIssue.detail}`);
    render();
    return;
  }

  const inputNode = findNode("input");
  const title = String(inputNode?.fields?.topic || "").trim();
  if (!title) {
    selectedId = "input";
    addLog("需要主题", "请先在“内容输入”步骤填写视频主题。");
    render();
    return;
  }

  runToken += 1;
  const currentRunToken = runToken;
  activeTask = null;
  activeTaskId = null;
  downloadedTaskId = "";
  clearTaskPolling();
  lastTaskSignature = "";
  resetGeneratedVideoState();
  resetRuntime({ keepLog: true, detachTask: false });
  isRunning = true;
  els.runLog.innerHTML = "";
  els.runTitle.textContent = "正在创建制作任务";

  const total = targetVideoCount();
  batchRunState = {
    total,
    nextIndex: 1,
    current: 1,
    completed: 0,
    failed: [],
    taskIds: {},
    skipFailed: batchQueueOptions.skipFailed,
    stopped: false,
    running: true,
    runToken: currentRunToken,
    title,
  };

  addLog("开始", total > 1 ? `准备批量生成 ${total} 条视频。` : "准备提交单条视频任务。");

  try {
    await launchBatchRound(1, total, currentRunToken);
  } catch (error) {
    isRunning = false;
    if (batchRunState) {
      batchRunState.running = false;
    }
    els.runTitle.textContent = "创建失败";
    addLog("创建失败", error.message || "无法创建制作任务。");
    render();
  }
}

function stopWorkflow() {
  clearTaskPolling();
  isRunning = false;
  if (batchRunState) {
    batchRunState.stopped = true;
    batchRunState.running = false;
  }
  addLog("停止", activeTaskId ? `已停止刷新，任务 ${activeTaskId} 可继续处理。` : "当前没有正在刷新的任务。");
  render();
}

async function clearCurrentWorkflow() {
  const taskId = activeTaskId || activeTask?.task_id || "";
  if (taskId && getAccessToken()) {
    try {
      const result = await apiRequest(`/tasks/${encodeURIComponent(taskId)}/clear`, {
        method: "POST",
        body: JSON.stringify({ clear_files: true }),
      });
      const removedCount = Array.isArray(result?.removed_files) ? result.removed_files.length : 0;
      if (result?.task) {
        rememberTask(result.task);
      }
      addLog("清空状态", removedCount ? `已清理 ${removedCount} 个文件。` : "已清空当前运行状态。");
    } catch (error) {
      addLog("清空状态", error.message || "清理失败，已重置本地状态。");
    }
  }
  downloadedTaskId = "";
  batchRunState = null;
  resetGeneratedVideoState();
  resetRuntime();
}

updateHorseSelectOptions();
render();
bindEvents();
loadHorseRagLibrary({ silent: false });
refreshProviderStatus({ silent: true });
refreshTaskList();
addLog("就绪", "视频创作流程已载入。");
