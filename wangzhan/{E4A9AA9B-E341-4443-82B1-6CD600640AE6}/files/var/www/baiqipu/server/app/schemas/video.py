from typing import Any

from pydantic import BaseModel, Field


class VideoCatalogItemOut(BaseModel):
    sequence: int
    name: str
    figure: str
    source: str
    story: str
    labels: list[str]


class VideoShotOut(BaseModel):
    scene: int
    visual: str
    subtitle: str


class VideoScriptOut(BaseModel):
    id: str
    horse_name: str
    style: str
    title: str
    opening: str
    body: str
    closing: str
    voiceover: str
    shots: list[VideoShotOut]
    estimated_seconds: int
    generation_mode: str
    model: str | None = None


class VideoGenerateScriptRequest(BaseModel):
    horse_name: str
    history: str = ""
    tags: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=lambda: ["emotional", "knowledge", "motivational"])
    count: int = Field(default=3, ge=1, le=6)
    duration: int = Field(default=30, ge=15, le=60)
    custom_text: str = ""


class VideoGenerateScriptOut(BaseModel):
    horse: VideoCatalogItemOut
    scripts: list[VideoScriptOut]


class VideoTTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    speed: float = Field(default=1.0, ge=0.5, le=1.5)


class VideoTTSOut(BaseModel):
    audio_url: str
    duration_seconds: float
    voice: str
    generation_mode: str


class VideoComposeRequest(BaseModel):
    horse_name: str
    script: VideoScriptOut
    style: str = "cinematic"
    duration: int = Field(default=30, ge=15, le=60)
    music: str = "epic"
    narration: bool = True
    voice: str = "zh-CN-XiaoxiaoNeural"
    audio_url: str | None = None
    subtitle: bool = True
    subtitle_style: str = "auto"
    scene_template: str = "chronicle"
    transition: str = "fade"
    background_mode: str = "auto"
    background_pack: str | None = None
    bgm_volume: float = Field(default=0.24, ge=0.0, le=1.0)
    ducking_threshold: float = Field(default=0.03, ge=0.005, le=1.0)
    ducking_ratio: float = Field(default=10.0, ge=1.0, le=24.0)
    ducking_attack_ms: int = Field(default=15, ge=1, le=500)
    ducking_release_ms: int = Field(default=850, ge=50, le=4000)


class VideoGenerateRequest(BaseModel):
    horse_id: str | None = None
    horse_name: str | None = None
    style: str = "cinematic"
    script_style: str = "emotional"
    duration: int = Field(default=30, ge=15, le=60)
    music: str = "epic"
    narration: bool = True
    subtitle: bool = True
    subtitle_style: str = "auto"
    voice: str = "zh-CN-XiaoxiaoNeural"
    custom_text: str = ""
    scene_template: str = "chronicle"
    transition: str = "fade"
    background_mode: str = "auto"
    background_pack: str | None = None
    bgm_volume: float = Field(default=0.24, ge=0.0, le=1.0)
    ducking_threshold: float = Field(default=0.03, ge=0.005, le=1.0)
    ducking_ratio: float = Field(default=10.0, ge=1.0, le=24.0)
    ducking_attack_ms: int = Field(default=15, ge=1, le=500)
    ducking_release_ms: int = Field(default=850, ge=50, le=4000)


class VideoBatchGenerateRequest(BaseModel):
    horse_names: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    style: str = "cinematic"
    script_style: str = "emotional"
    duration: int = Field(default=30, ge=15, le=60)
    music: str = "epic"
    narration: bool = True
    subtitle: bool = True
    subtitle_style: str = "auto"
    voice: str = "zh-CN-XiaoxiaoNeural"
    custom_text: str = ""
    scene_template: str = "chronicle"
    transition: str = "fade"
    background_mode: str = "auto"
    background_pack: str | None = None
    bgm_volume: float = Field(default=0.24, ge=0.0, le=1.0)
    ducking_threshold: float = Field(default=0.03, ge=0.005, le=1.0)
    ducking_ratio: float = Field(default=10.0, ge=1.0, le=24.0)
    ducking_attack_ms: int = Field(default=15, ge=1, le=500)
    ducking_release_ms: int = Field(default=850, ge=50, le=4000)


class VideoBatchFailureOut(BaseModel):
    horse_name: str
    detail: str


class VideoRetryRequest(BaseModel):
    rebuild_audio: bool = False


class VideoBackgroundAssetOut(BaseModel):
    id: str
    name: str
    description: str
    scene_index: int
    file_url: str


class VideoBackgroundPackOut(BaseModel):
    id: str
    name: str
    description: str
    recommended_templates: list[str]
    semantic_tags: list[str] = Field(default_factory=list)
    match_hint: str = ""
    asset_count: int
    preview_url: str
    assets: list[VideoBackgroundAssetOut]


class VideoSubtitleSegmentOut(BaseModel):
    scene: int
    text: str
    start_seconds: float
    end_seconds: float


class VideoTaskOut(BaseModel):
    task_id: str
    horse_id: str | None = None
    horse_name: str
    status: str
    progress: int = 0
    style: str
    script_style: str
    duration: int
    music: str
    narration: bool
    voice: str
    scene_template: str | None = None
    transition: str | None = None
    background_mode: str | None = None
    background_pack: str | None = None
    background_pack_name: str | None = None
    background_preview_url: str | None = None
    background_assets: list[str] = Field(default_factory=list)
    background_match_mode: str | None = None
    background_match_reason: str | None = None
    background_match_tags: list[str] = Field(default_factory=list)
    subtitle_enabled: bool | None = None
    subtitle_style: str | None = None
    subtitle_style_name: str | None = None
    generation_mode: str | None = None
    batch_id: str | None = None
    attempt: int = 1
    script: VideoScriptOut | None = None
    audio_url: str | None = None
    bgm_url: str | None = None
    audio_mix_mode: str | None = None
    bgm_volume: float | None = None
    ducking_threshold: float | None = None
    ducking_ratio: float | None = None
    ducking_attack_ms: int | None = None
    ducking_release_ms: int | None = None
    subtitle_url: str | None = None
    subtitle_segments: list[VideoSubtitleSegmentOut] = Field(default_factory=list)
    video_url: str | None = None
    thumbnail_url: str | None = None
    cover_url: str | None = None
    created_at: str
    updated_at: str | None = None
    estimated_seconds: int = 120
    error_message: str | None = None


class VideoBatchGenerateOut(BaseModel):
    batch_id: str | None = None
    tasks: list[VideoTaskOut]
    failures: list[VideoBatchFailureOut] = Field(default_factory=list)


class VideoOptionsOut(BaseModel):
    styles: list[dict[str, Any]]
    script_styles: list[dict[str, Any]]
    music_options: list[dict[str, Any]]
    subtitle_style_options: list[dict[str, Any]]
    duration_options: list[dict[str, Any]]
    voice_options: list[dict[str, Any]]
    template_options: list[dict[str, Any]]
    transition_options: list[dict[str, Any]]
    background_packs: list[VideoBackgroundPackOut]
    audio_mix_defaults: dict[str, Any]
