from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.horse import Horse
from app.models.user import User
from app.models.video import VideoTask
from app.schemas.video import (
    VideoBatchGenerateOut,
    VideoBatchGenerateRequest,
    VideoBatchFailureOut,
    VideoCatalogItemOut,
    VideoComposeRequest,
    VideoGenerateRequest,
    VideoGenerateScriptOut,
    VideoGenerateScriptRequest,
    VideoOptionsOut,
    VideoRetryRequest,
    VideoTTSOut,
    VideoTTSRequest,
    VideoTaskOut,
)
from app.services.auth import get_current_user
from app.services.background_library import list_background_packs
from app.services.script_gen import (
    ScriptGenerationError,
    build_db_horse_profile,
    generate_script_variants,
    load_video_catalog,
    resolve_horse_profile,
)
from app.services.video_factory import (
    advance_video_task,
    build_compose_payload,
    build_tts_artifact,
    enqueue_video_task,
    get_audio_mix_defaults,
    list_subtitle_style_options,
    serialize_video_task,
)

router = APIRouter(prefix="/video", tags=["video-factory"])


def _resolve_horse_input(
    db: Session,
    *,
    horse_name: str | None = None,
    horse_id: str | None = None,
) -> tuple[Horse | None, dict]:
    db_horse = None
    if horse_id:
        db_horse = db.query(Horse).filter(Horse.id == horse_id).first()
        if not db_horse and not horse_name:
            raise HTTPException(status_code=404, detail="Horse not found")

    resolved_name = horse_name or (db_horse.name if db_horse else None)
    if not resolved_name:
        raise HTTPException(status_code=400, detail="horse_name or horse_id is required")

    try:
        profile = resolve_horse_profile(resolved_name)
    except ScriptGenerationError:
        if db_horse:
            profile = build_db_horse_profile(db_horse)
        else:
            raise HTTPException(status_code=404, detail="Horse not found in video catalog")

    return db_horse, profile


def _create_task(
    db: Session,
    user: User,
    *,
    horse_id: str | None,
    horse_name: str,
    horse_profile: dict,
    visual_style: str,
    script_style: str,
    duration: int,
    music: str,
    narration: bool,
    voice: str,
    custom_text: str,
    script_payload: dict,
    tts_payload: dict,
    scene_template: str = "chronicle",
    transition: str = "fade",
    background_mode: str = "auto",
    background_pack: str | None = None,
    subtitle_enabled: bool = True,
    subtitle_style: str = "auto",
    bgm_volume: float = 0.24,
    ducking_threshold: float = 0.03,
    ducking_ratio: float = 10.0,
    ducking_attack_ms: int = 15,
    ducking_release_ms: int = 850,
    batch_id: str | None = None,
    attempt: int = 1,
) -> VideoTask:
    task_id = f"vid_{uuid.uuid4().hex[:12]}"
    compose_payload = build_compose_payload(
        task_id=task_id,
        horse_name=horse_name,
        visual_style=visual_style,
        script_title=script_payload.get("title", horse_name),
        duration=duration,
        music=music,
        transition=transition,
        scene_template=scene_template,
        background_mode=background_mode,
        background_pack=background_pack,
        subtitle_enabled=subtitle_enabled,
        subtitle_style=subtitle_style,
        bgm_volume=bgm_volume,
        ducking_threshold=ducking_threshold,
        ducking_ratio=ducking_ratio,
        ducking_attack_ms=ducking_attack_ms,
        ducking_release_ms=ducking_release_ms,
        horse_profile=horse_profile,
        batch_id=batch_id,
        attempt=attempt,
    )
    compose_payload.pop("video_url", None)

    task = VideoTask(
        id=task_id,
        user_id=user.id,
        horse_id=horse_id,
        horse_name=horse_name,
        status="queued",
        progress=5,
        visual_style=visual_style,
        script_style=script_style,
        duration=duration,
        music=music,
        narration=narration,
        voice=voice,
        custom_text=custom_text,
        estimated_seconds=max(duration * 6, 45),
        script_payload=script_payload,
        tts_payload=tts_payload,
        compose_payload=compose_payload,
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _reset_failed_task(
    db: Session,
    task: VideoTask,
    *,
    rebuild_audio: bool = False,
) -> VideoTask:
    script_payload = dict(task.script_payload or {})
    compose_payload = dict(task.compose_payload or {})
    attempt = int(compose_payload.get("attempt") or 1) + 1
    batch_id = compose_payload.get("batch_id")
    transition = str(compose_payload.get("transition") or "fade")
    scene_template = str(compose_payload.get("scene_template") or "chronicle")
    background_mode = str(compose_payload.get("background_mode") or "auto")
    background_pack = compose_payload.get("background_pack")
    subtitle_enabled = bool(compose_payload.get("subtitle_enabled", True))
    subtitle_style = str(compose_payload.get("subtitle_style") or "auto")
    horse_profile = compose_payload.get("horse_profile") if isinstance(compose_payload.get("horse_profile"), dict) else {}

    next_tts_payload = dict(task.tts_payload or {})
    if rebuild_audio and task.narration:
        voiceover = str(script_payload.get("voiceover", "")).strip()
        if voiceover:
            next_tts_payload = build_tts_artifact(voiceover, task.voice, 1.0)

    refreshed_payload = build_compose_payload(
        task_id=task.id,
        horse_name=task.horse_name,
        visual_style=task.visual_style,
        script_title=str(script_payload.get("title") or task.horse_name),
        duration=task.duration,
        music=task.music,
        transition=transition,
        scene_template=scene_template,
        background_mode=background_mode,
        background_pack=background_pack,
        subtitle_enabled=subtitle_enabled,
        subtitle_style=subtitle_style,
        bgm_volume=float(compose_payload.get("bgm_volume") or 0.24),
        ducking_threshold=float(compose_payload.get("ducking_threshold") or 0.03),
        ducking_ratio=float(compose_payload.get("ducking_ratio") or 10.0),
        ducking_attack_ms=int(compose_payload.get("ducking_attack_ms") or 15),
        ducking_release_ms=int(compose_payload.get("ducking_release_ms") or 850),
        horse_profile=horse_profile,
        batch_id=batch_id,
        attempt=attempt,
    )
    refreshed_payload.pop("video_url", None)

    task.status = "queued"
    task.progress = 5
    task.error_message = None
    task.estimated_seconds = max(task.duration * 6, 45)
    task.tts_payload = next_tts_payload
    task.compose_payload = refreshed_payload
    task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/catalog", response_model=list[VideoCatalogItemOut])
def get_video_catalog():
    return load_video_catalog()


@router.post("/generate-script", response_model=VideoGenerateScriptOut)
def generate_script(
    req: VideoGenerateScriptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _, profile = _resolve_horse_input(db, horse_name=req.horse_name)
    horse, scripts = generate_script_variants(
        profile["name"],
        history=req.history,
        tags=req.tags,
        styles=req.styles,
        count=req.count,
        duration=req.duration,
        custom_text=req.custom_text,
        profile_override=profile,
    )
    return VideoGenerateScriptOut(horse=horse, scripts=scripts)


@router.post("/tts", response_model=VideoTTSOut)
def synthesize_video_voice(
    req: VideoTTSRequest,
    user: User = Depends(get_current_user),
):
    return VideoTTSOut(**build_tts_artifact(req.text, req.voice, req.speed))


@router.post("/compose", response_model=VideoTaskOut)
def compose_video(
    req: VideoComposeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _, profile = _resolve_horse_input(db, horse_name=req.horse_name)
    tts_payload: dict = {}
    if req.narration:
        tts_payload = build_tts_artifact(req.script.voiceover, req.voice, 1.0)
        if req.audio_url:
            tts_payload["audio_url"] = req.audio_url

    task = _create_task(
        db,
        user,
        horse_id=None,
        horse_name=profile["name"],
        horse_profile=profile,
        visual_style=req.style,
        script_style=req.script.style,
        duration=req.duration,
        music=req.music,
        narration=req.narration,
        voice=req.voice,
        custom_text="",
        script_payload=req.script.model_dump(),
        tts_payload=tts_payload,
        scene_template=req.scene_template,
        transition=req.transition,
        background_mode=req.background_mode,
        background_pack=req.background_pack,
        subtitle_enabled=req.subtitle,
        subtitle_style=req.subtitle_style,
        bgm_volume=req.bgm_volume,
        ducking_threshold=req.ducking_threshold,
        ducking_ratio=req.ducking_ratio,
        ducking_attack_ms=req.ducking_attack_ms,
        ducking_release_ms=req.ducking_release_ms,
    )
    enqueue_video_task(task.id)
    return VideoTaskOut(**serialize_video_task(task))


@router.post("/generate", response_model=VideoTaskOut)
def generate_video(
    req: VideoGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db_horse, profile = _resolve_horse_input(db, horse_name=req.horse_name, horse_id=req.horse_id)
    _, scripts = generate_script_variants(
        profile["name"],
        history=profile["story"],
        tags=profile["labels"],
        styles=[req.script_style],
        count=1,
        duration=req.duration,
        custom_text=req.custom_text,
        profile_override=profile,
    )
    selected_script = scripts[0]
    tts_payload: dict = {}
    if req.narration:
        tts_payload = build_tts_artifact(selected_script["voiceover"], req.voice, 1.0)

    task = _create_task(
        db,
        user,
        horse_id=db_horse.id if db_horse else req.horse_id,
        horse_name=profile["name"],
        horse_profile=profile,
        visual_style=req.style,
        script_style=req.script_style,
        duration=req.duration,
        music=req.music,
        narration=req.narration,
        voice=req.voice,
        custom_text=req.custom_text,
        script_payload=selected_script,
        tts_payload=tts_payload,
        scene_template=req.scene_template,
        transition=req.transition,
        background_mode=req.background_mode,
        background_pack=req.background_pack,
        subtitle_enabled=req.subtitle,
        subtitle_style=req.subtitle_style,
        bgm_volume=req.bgm_volume,
        ducking_threshold=req.ducking_threshold,
        ducking_ratio=req.ducking_ratio,
        ducking_attack_ms=req.ducking_attack_ms,
        ducking_release_ms=req.ducking_release_ms,
    )
    enqueue_video_task(task.id)
    return VideoTaskOut(**serialize_video_task(task))


@router.post("/batch-generate", response_model=VideoBatchGenerateOut)
def generate_video_batch(
    req: VideoBatchGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    batch_id = f"batch_{uuid.uuid4().hex[:10]}"
    tasks: list[VideoTask] = []
    failures: list[VideoBatchFailureOut] = []
    seen: set[str] = set()
    normalized_horses = [name.strip() for name in req.horse_names if name.strip()]

    if not normalized_horses:
        raise HTTPException(status_code=400, detail="horse_names is required")

    for horse_name in normalized_horses:
        if horse_name in seen:
            continue
        seen.add(horse_name)

        try:
            db_horse, profile = _resolve_horse_input(db, horse_name=horse_name)
            _, scripts = generate_script_variants(
                profile["name"],
                history=profile["story"],
                tags=profile["labels"],
                styles=[req.script_style],
                count=1,
                duration=req.duration,
                custom_text=req.custom_text,
                profile_override=profile,
            )
            selected_script = scripts[0]
            tts_payload: dict = {}
            if req.narration:
                tts_payload = build_tts_artifact(selected_script["voiceover"], req.voice, 1.0)

            task = _create_task(
                db,
                user,
                horse_id=db_horse.id if db_horse else None,
                horse_name=profile["name"],
                horse_profile=profile,
                visual_style=req.style,
                script_style=req.script_style,
                duration=req.duration,
                music=req.music,
                narration=req.narration,
                voice=req.voice,
                custom_text=req.custom_text,
                script_payload=selected_script,
                tts_payload=tts_payload,
                scene_template=req.scene_template,
                transition=req.transition,
                background_mode=req.background_mode,
                background_pack=req.background_pack,
                subtitle_enabled=req.subtitle,
                subtitle_style=req.subtitle_style,
                bgm_volume=req.bgm_volume,
                ducking_threshold=req.ducking_threshold,
                ducking_ratio=req.ducking_ratio,
                ducking_attack_ms=req.ducking_attack_ms,
                ducking_release_ms=req.ducking_release_ms,
                batch_id=batch_id,
            )
            tasks.append(task)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Failed to prepare task"
            failures.append(VideoBatchFailureOut(horse_name=horse_name, detail=detail))
        except Exception as exc:
            failures.append(VideoBatchFailureOut(horse_name=horse_name, detail=str(exc)))

    for task in tasks:
        enqueue_video_task(task.id)

    return VideoBatchGenerateOut(
        batch_id=batch_id if tasks else None,
        tasks=[VideoTaskOut(**serialize_video_task(task)) for task in tasks],
        failures=failures,
    )


@router.post("/retry/{task_id}", response_model=VideoTaskOut)
def retry_video_task(
    task_id: str,
    req: VideoRetryRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(VideoTask).filter(VideoTask.id == task_id, VideoTask.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed tasks can be retried")

    refreshed = _reset_failed_task(db, task, rebuild_audio=bool(req and req.rebuild_audio))
    enqueue_video_task(refreshed.id)
    return VideoTaskOut(**serialize_video_task(refreshed))


@router.get("/status/{task_id}", response_model=VideoTaskOut)
def get_video_status(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(VideoTask).filter(VideoTask.id == task_id, VideoTask.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    advance_video_task(task)
    db.refresh(task)
    return VideoTaskOut(**serialize_video_task(task))


@router.get("/history", response_model=list[VideoTaskOut])
def list_videos(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tasks = (
        db.query(VideoTask)
        .filter(VideoTask.user_id == user.id)
        .order_by(VideoTask.created_at.desc(), VideoTask.id.desc())
        .all()
    )
    return [VideoTaskOut(**serialize_video_task(task)) for task in tasks]


@router.get("/options", response_model=VideoOptionsOut)
def get_video_options():
    return VideoOptionsOut(
        styles=[
            {"id": "ink", "name": "东方水墨", "description": "沉稳克制，适合历史厚重感和名马气质。"},
            {"id": "cinematic", "name": "史诗电影", "description": "高对比金棕色调，适合英雄叙事和成片展示。"},
            {"id": "anime", "name": "国风动画", "description": "轮廓鲜明、节奏更快，适合少年将气质和短视频传播。"},
            {"id": "watercolor", "name": "淡彩长卷", "description": "柔和留白，适合人物故事型文案。"},
        ],
        script_styles=[
            {"id": "emotional", "name": "情绪叙事", "description": "突出命运感、人物情感与英雄气场。"},
            {"id": "knowledge", "name": "知识讲述", "description": "偏史料解读，适合口播介绍和知识卡点。"},
            {"id": "motivational", "name": "热血激励", "description": "强调成长、逆境和精神鼓舞。"},
        ],
        music_options=[
            {"id": "traditional", "name": "国风器乐", "description": "贴近百骑谱世界观，适合大多数名马题材。"},
            {"id": "epic", "name": "史诗鼓点", "description": "适合冲阵、王朝开创和高能转场。"},
            {"id": "calm", "name": "沉静氛围", "description": "适合缓慢讲述、人物志和典藏向表达。"},
        ],
        subtitle_style_options=list_subtitle_style_options(),
        duration_options=[
            {"id": 15, "name": "15 秒", "description": "高密度短视频节奏，适合传播向内容。"},
            {"id": 30, "name": "30 秒", "description": "信息与节奏均衡，适合主力成片。"},
            {"id": 60, "name": "60 秒", "description": "适合完整故事线和更强情绪铺垫。"},
        ],
        voice_options=[
            {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "description": "清晰稳定，适合多数知识讲述脚本。"},
            {"id": "zh-CN-YunxiNeural", "name": "云希", "description": "年轻明亮，适合热血与少年将气质。"},
            {"id": "zh-CN-YunjianNeural", "name": "云健", "description": "厚重沉稳，适合帝王、名将与史诗旁白。"},
        ],
        template_options=[
            {"id": "chronicle", "name": "纪传长卷", "description": "像翻阅史书，适合人物与名马共叙。"},
            {"id": "battle", "name": "冲阵战报", "description": "节奏更强，强调推进、爆发和压迫感。"},
            {"id": "legend", "name": "传说藏卷", "description": "更像高阶收藏卡，适合稀有名马和传说卡位。"},
        ],
        transition_options=[
            {"id": "fade", "name": "淡入淡出", "description": "最稳定，适合大部分历史叙事。"},
            {"id": "slideleft", "name": "横向推镜", "description": "画面更有推进感，适合战场与奔袭。"},
            {"id": "wipeleft", "name": "卷轴擦除", "description": "像翻页换镜，适合纪传和档案结构。"},
            {"id": "circleopen", "name": "镜门开启", "description": "更戏剧化，适合传说卡和高位名马。"},
        ],
        background_packs=list_background_packs(),
        audio_mix_defaults=get_audio_mix_defaults(),
    )
    return VideoOptionsOut(
        styles=[
            {"id": "cinematic", "name": "史诗电影", "description": "高对比、金棕色调，适合英雄叙事和成片展示。"},
            {"id": "anime", "name": "热血动画", "description": "轮廓更鲜明，适合少年将和冲锋镜头。"},
            {"id": "watercolor", "name": "水彩长卷", "description": "柔和笔触与留白，更适合人物故事型文案。"},
            {"id": "ink", "name": "东方水墨", "description": "沉稳克制，适合历史厚重感和名马气质。"},
        ],
        script_styles=[
            {"id": "emotional", "name": "情绪叙事", "description": "突出命运感、人物情感与英雄气场。"},
            {"id": "knowledge", "name": "知识讲述", "description": "偏史料解说，适合做短视频口播与介绍卡。"},
            {"id": "motivational", "name": "热血激励", "description": "强调成长、逆境和精神鼓舞。"},
        ],
        music_options=[
            {"id": "epic", "name": "史诗鼓点", "description": "适合冲阵、王朝开创和高能转场。"},
            {"id": "calm", "name": "沉静氛围", "description": "适合缓慢讲述、人物志和典藏向表达。"},
            {"id": "traditional", "name": "国风器乐", "description": "更贴近百骑谱世界观，适合大部分名马题材。"},
        ],
        subtitle_style_options=list_subtitle_style_options(),
        duration_options=[
            {"id": 15, "name": "15 秒", "description": "高密度短视频节奏，适合传播向内容。"},
            {"id": 30, "name": "30 秒", "description": "信息与节奏均衡，适合主力成片。"},
            {"id": 60, "name": "60 秒", "description": "适合完整故事线与更强的情绪铺垫。"},
        ],
        voice_options=[
            {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "description": "清晰稳定，适合大多数知识讲述脚本。"},
            {"id": "zh-CN-YunxiNeural", "name": "云希", "description": "更年轻明亮，适合热血与少年将气质。"},
            {"id": "zh-CN-YunjianNeural", "name": "云健", "description": "更厚重沉稳，适合帝王、名将与史诗旁白。"},
        ],
        template_options=[
            {"id": "chronicle", "name": "纪传长卷", "description": "像在翻阅史书，适合人物与名马共叙。"},
            {"id": "battle", "name": "冲阵战报", "description": "节奏更强，强调推进、爆发和压迫感。"},
            {"id": "legend", "name": "传说藏卷", "description": "更像高阶收藏卡，适合稀有名马和传说卡位。"},
        ],
        transition_options=[
            {"id": "fade", "name": "淡入淡出", "description": "最稳妥，适合大部分历史叙事。"},
            {"id": "slideleft", "name": "横向推镜", "description": "画面更有推进感，适合战场与奔袭。"},
            {"id": "wipeleft", "name": "卷轴擦除", "description": "像翻页换镜，适合纪传和档案结构。"},
            {"id": "circleopen", "name": "镜门开启", "description": "更戏剧化，适合传说卡和高位名马。"},
        ],
        background_packs=list_background_packs(),
        audio_mix_defaults=get_audio_mix_defaults(),
    )
