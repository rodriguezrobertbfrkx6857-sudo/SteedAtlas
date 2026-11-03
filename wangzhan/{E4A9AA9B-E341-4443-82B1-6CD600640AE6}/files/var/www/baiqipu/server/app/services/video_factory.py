from __future__ import annotations

import hashlib
import html
import math
import os
import struct
import subprocess
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.database import SessionLocal
from app.models.video import VideoTask
from app.services import tts as tts_service
from app.services.background_library import recommend_background_pack, resolve_background_assets

SERVER_DIR = Path(__file__).resolve().parents[2]
GENERATED_DIR = SERVER_DIR / "generated"
AUDIO_DIR = GENERATED_DIR / "audio"
MUSIC_DIR = GENERATED_DIR / "music"
SUBTITLE_DIR = GENERATED_DIR / "subtitles"
THUMBNAIL_DIR = GENERATED_DIR / "thumbnails"
VIDEO_DIR = GENERATED_DIR / "videos"
TEXT_DIR = GENERATED_DIR / "text"
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
FPS = 30
AUDIO_SAMPLE_RATE = 22050

settings = get_settings()
FFMPEG_BIN = settings.BAIQIPU_FFMPEG_BIN or "ffmpeg"
VIDEO_QUEUE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="baiqipu-video")
_ENQUEUED_TASKS: set[str] = set()
_QUEUE_LOCK = threading.Lock()

SCENE_TEMPLATE_PRESETS: dict[str, dict[str, Any]] = {
    "chronicle": {
        "label": "纪传长卷",
        "default_transition": "fade",
        "accent": "0xE2B665",
        "text": "0xFFF4DD",
        "muted": "0xE7D3AE",
        "panel": "black@0.34",
        "frame": "white@0.18",
    },
    "battle": {
        "label": "冲阵战报",
        "default_transition": "slideleft",
        "accent": "0xF26A4B",
        "text": "0xFFF1E1",
        "muted": "0xFFCCB2",
        "panel": "black@0.28",
        "frame": "white@0.14",
    },
    "legend": {
        "label": "传说藏卷",
        "default_transition": "circleopen",
        "accent": "0xD7C38E",
        "text": "0xF8F4EA",
        "muted": "0xD3E0F1",
        "panel": "black@0.24",
        "frame": "white@0.18",
    },
}

TRANSITION_ALIASES = {
    "fade": "fade",
    "slide": "slideleft",
    "slideleft": "slideleft",
    "wipe": "wipeleft",
    "wipeleft": "wipeleft",
    "circle": "circleopen",
    "circleopen": "circleopen",
}

SUBTITLE_STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "scroll-emblem": {
        "label": "金卷题签",
        "description": "居中金色字幕条，更适合纪传长卷与史传叙事。",
        "font_size": 30,
        "font_color": "0xFFF4DD",
        "box_color": "black@0.46",
        "box_border": 24,
        "line_spacing": 10,
        "border_width": 1.2,
        "border_color": "0xE2B665",
        "shadow_color": "black@0.70",
        "shadow_x": 2,
        "shadow_y": 2,
        "x": "(w-text_w)/2",
        "y": "h-170",
    },
    "battle-banner": {
        "label": "战报横幅",
        "description": "更厚重的战报字幕，适合冲阵、奔袭和战场高压镜头。",
        "font_size": 31,
        "font_color": "0xFFF1E1",
        "box_color": "0x1C0D0A@0.72",
        "box_border": 26,
        "line_spacing": 10,
        "border_width": 1.6,
        "border_color": "0xF26A4B",
        "shadow_color": "black@0.82",
        "shadow_x": 2,
        "shadow_y": 3,
        "x": "88",
        "y": "h-182",
    },
    "legend-glow": {
        "label": "月光题咏",
        "description": "居中发光字幕，适合传说、神话和稀有名马的高位镜头。",
        "font_size": 29,
        "font_color": "0xF8F4EA",
        "box_color": "0x07111E@0.40",
        "box_border": 20,
        "line_spacing": 10,
        "border_width": 1.0,
        "border_color": "0xD7C38E",
        "shadow_color": "0x10243F@0.90",
        "shadow_x": 0,
        "shadow_y": 0,
        "x": "(w-text_w)/2",
        "y": "h-194",
    },
    "clean-lower-third": {
        "label": "简洁下三分之一",
        "description": "更现代的下三分之一字幕条，适合知识卡点和混合风格成片。",
        "font_size": 28,
        "font_color": "white",
        "box_color": "black@0.42",
        "box_border": 18,
        "line_spacing": 8,
        "border_width": 0.8,
        "border_color": "white@0.28",
        "shadow_color": "black@0.72",
        "shadow_x": 2,
        "shadow_y": 2,
        "x": "(w-text_w)/2",
        "y": "h-150",
    },
}

TEMPLATE_SUBTITLE_STYLE = {
    "chronicle": "scroll-emblem",
    "battle": "battle-banner",
    "legend": "legend-glow",
}

AUDIO_MIX_DEFAULTS = {
    "bgm_volume": 0.24,
    "ducking_threshold": 0.03,
    "ducking_ratio": 10.0,
    "ducking_attack_ms": 15,
    "ducking_release_ms": 850,
}

SCENE_TEMPLATE_PRESETS.update(
    {
        "chronicle": {
            **SCENE_TEMPLATE_PRESETS["chronicle"],
            "label": "纪传长卷",
            "default_transition": "fade",
        },
        "battle": {
            **SCENE_TEMPLATE_PRESETS["battle"],
            "label": "冲阵战报",
            "default_transition": "slideleft",
        },
        "legend": {
            **SCENE_TEMPLATE_PRESETS["legend"],
            "label": "传说藏卷",
            "default_transition": "circleopen",
        },
    }
)

SUBTITLE_STYLE_PRESETS.update(
    {
        "scroll-emblem": {
            **SUBTITLE_STYLE_PRESETS["scroll-emblem"],
            "label": "金卷题签",
            "description": "居中金色字幕条，适合纪传长卷与史传叙事。",
        },
        "battle-banner": {
            **SUBTITLE_STYLE_PRESETS["battle-banner"],
            "label": "战报横幅",
            "description": "更厚重的战报字幕，适合冲阵、奔袭和高压镜头。",
        },
        "legend-glow": {
            **SUBTITLE_STYLE_PRESETS["legend-glow"],
            "label": "月光题咏",
            "description": "居中发光字幕，适合传说、神话和稀有名马。",
        },
        "clean-lower-third": {
            **SUBTITLE_STYLE_PRESETS["clean-lower-third"],
            "label": "简洁下三分之一",
            "description": "更现代的字幕条，适合知识卡点和混合风格成片。",
        },
    }
)


def ensure_generated_dirs() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)


def _estimate_audio_duration(text: str, speed: float) -> float:
    normalized = "".join(text.split())
    base_seconds = max(6.0, len(normalized) / 5.5)
    return round(base_seconds / max(speed, 0.5), 1)


def build_tts_artifact(text: str, voice: str, speed: float = 1.0) -> dict[str, Any]:
    ensure_generated_dirs()
    artifact_id = hashlib.md5(f"{voice}:{speed}:{text}".encode("utf-8")).hexdigest()[:16]
    duration_seconds = _estimate_audio_duration(text, speed)

    try:
        audio_bytes = tts_service.synthesize_text(text, voice=voice)
    except Exception:
        return {
            "audio_url": f"mock://tts/{artifact_id}.mp3",
            "duration_seconds": duration_seconds,
            "voice": voice,
            "generation_mode": "placeholder",
        }

    audio_path = AUDIO_DIR / f"{artifact_id}.mp3"
    audio_path.write_bytes(audio_bytes)
    return {
        "audio_url": f"/generated/audio/{audio_path.name}",
        "duration_seconds": duration_seconds,
        "voice": voice,
        "generation_mode": "azure",
    }


def _resolve_scene_template_id(template_id: str | None) -> str:
    normalized = str(template_id or "").strip().lower()
    if normalized in SCENE_TEMPLATE_PRESETS:
        return normalized
    return "chronicle"


def _resolve_scene_template(template_id: str | None) -> dict[str, Any]:
    return SCENE_TEMPLATE_PRESETS[_resolve_scene_template_id(template_id)]


def _resolve_transition(transition: str | None, template_id: str | None) -> str:
    preset = _resolve_scene_template(template_id)
    normalized = str(transition or "").strip().lower()
    if normalized in TRANSITION_ALIASES:
        return TRANSITION_ALIASES[normalized]
    return str(preset["default_transition"])


def _normalize_background_mode(mode: str | None) -> str:
    return "manual" if str(mode or "").strip().lower() == "manual" else "auto"


def _clamp_float(value: float | int | None, minimum: float, maximum: float) -> float:
    try:
        number = float(value if value is not None else minimum)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _clamp_int(value: int | float | None, minimum: int, maximum: int) -> int:
    try:
        number = int(round(float(value if value is not None else minimum)))
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _normalize_audio_mix_settings(
    *,
    bgm_volume: float | None = None,
    ducking_threshold: float | None = None,
    ducking_ratio: float | None = None,
    ducking_attack_ms: int | None = None,
    ducking_release_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "bgm_volume": round(_clamp_float(bgm_volume, 0.0, 1.0), 2),
        "ducking_threshold": round(_clamp_float(ducking_threshold, 0.005, 1.0), 3),
        "ducking_ratio": round(_clamp_float(ducking_ratio, 1.0, 24.0), 2),
        "ducking_attack_ms": _clamp_int(ducking_attack_ms, 1, 500),
        "ducking_release_ms": _clamp_int(ducking_release_ms, 50, 4000),
    }


def _resolve_subtitle_style_id(style_id: str | None, template_id: str | None) -> str:
    normalized = str(style_id or "").strip().lower()
    if normalized in SUBTITLE_STYLE_PRESETS:
        return normalized
    return TEMPLATE_SUBTITLE_STYLE.get(_resolve_scene_template_id(template_id), "scroll-emblem")


def _resolve_subtitle_style(style_id: str | None, template_id: str | None) -> dict[str, Any]:
    resolved_id = _resolve_subtitle_style_id(style_id, template_id)
    return {
        "id": resolved_id,
        **SUBTITLE_STYLE_PRESETS[resolved_id],
    }


def list_subtitle_style_options() -> list[dict[str, Any]]:
    return [
        {
            "id": style_id,
            "name": str(preset["label"]),
            "description": str(preset["description"]),
        }
        for style_id, preset in SUBTITLE_STYLE_PRESETS.items()
    ]


def get_audio_mix_defaults() -> dict[str, Any]:
    return dict(AUDIO_MIX_DEFAULTS)


def _write_placeholder_thumbnail(
    task_id: str,
    horse_name: str,
    visual_style: str,
    script_title: str,
    scene_template: str,
    background_pack_name: str,
) -> str:
    ensure_generated_dirs()
    preset = _resolve_scene_template(scene_template)
    safe_title = html.escape(script_title[:38])
    safe_name = html.escape(horse_name)
    safe_style = html.escape(visual_style)
    safe_template = html.escape(str(preset["label"]))
    safe_pack_name = html.escape(background_pack_name)
    thumbnail_path = THUMBNAIL_DIR / f"{task_id}.svg"
    thumbnail_path.write_text(
        "\n".join(
            [
                "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='675' viewBox='0 0 1200 675'>",
                "  <defs>",
                "    <linearGradient id='bg' x1='0%' y1='0%' x2='100%' y2='100%'>",
                "      <stop offset='0%' stop-color='#120d06' />",
                "      <stop offset='55%' stop-color='#8a5a18' />",
                "      <stop offset='100%' stop-color='#f2d396' />",
                "    </linearGradient>",
                "  </defs>",
                "  <rect width='1200' height='675' fill='url(#bg)' />",
                "  <rect x='48' y='48' width='1104' height='579' rx='28' fill='rgba(10,10,10,0.42)' stroke='rgba(255,248,220,0.38)' />",
                "  <text x='90' y='136' fill='#f8e7c4' font-size='30' font-family='Microsoft YaHei, sans-serif'>百骑谱 · AI 视频工厂</text>",
                f"  <text x='90' y='260' fill='#fff7dc' font-size='96' font-family='Microsoft YaHei, sans-serif' font-weight='700'>{safe_name}</text>",
                f"  <text x='90' y='338' fill='#f8e7c4' font-size='32' font-family='Microsoft YaHei, sans-serif'>{safe_template} / {safe_style}</text>",
                f"  <text x='90' y='408' fill='#fdf4df' font-size='42' font-family='Microsoft YaHei, sans-serif'>{safe_title}</text>",
                f"  <text x='90' y='492' fill='#f8e7c4' font-size='28' font-family='Microsoft YaHei, sans-serif'>素材库：{safe_pack_name}</text>",
                "  <text x='90' y='548' fill='#f8e7c4' font-size='28' font-family='Microsoft YaHei, sans-serif'>已进入视频队列，正在装配真实背景素材和转场成片。</text>",
                "</svg>",
            ]
        ),
        encoding="utf-8",
    )
    return f"/generated/thumbnails/{thumbnail_path.name}"


def build_compose_payload(
    task_id: str,
    horse_name: str,
    visual_style: str,
    script_title: str,
    duration: int,
    music: str,
    transition: str,
    scene_template: str = "chronicle",
    background_pack: str | None = None,
    background_mode: str = "auto",
    subtitle_enabled: bool = True,
    subtitle_style: str = "auto",
    bgm_volume: float | None = None,
    ducking_threshold: float | None = None,
    ducking_ratio: float | None = None,
    ducking_attack_ms: int | None = None,
    ducking_release_ms: int | None = None,
    horse_profile: dict[str, Any] | None = None,
    batch_id: str | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    template_id = _resolve_scene_template_id(scene_template)
    template = _resolve_scene_template(template_id)
    resolved_subtitle_style = _resolve_subtitle_style(subtitle_style, template_id)
    audio_mix_settings = _normalize_audio_mix_settings(
        bgm_volume=bgm_volume,
        ducking_threshold=ducking_threshold,
        ducking_ratio=ducking_ratio,
        ducking_attack_ms=ducking_attack_ms,
        ducking_release_ms=ducking_release_ms,
    )
    normalized_background_mode = _normalize_background_mode(background_mode)
    requested_pack = background_pack if normalized_background_mode == "manual" else None
    pack, recommendation = recommend_background_pack(requested_pack, template_id, horse_profile=horse_profile)
    normalized_transition = _resolve_transition(transition, template_id)
    asset_urls = [str(asset["file_url"]) for asset in pack.get("assets", [])]
    thumbnail_url = _write_placeholder_thumbnail(
        task_id,
        horse_name,
        visual_style,
        script_title,
        template_id,
        str(pack["name"]),
    )
    return {
        "video_url": None,
        "thumbnail_url": thumbnail_url,
        "cover_url": thumbnail_url,
        "duration": duration,
        "music": music,
        "transition": normalized_transition,
        "scene_template": template_id,
        "scene_template_label": template["label"],
        "background_mode": normalized_background_mode,
        "background_pack": pack["id"],
        "background_pack_name": pack["name"],
        "background_preview_url": pack["preview_url"],
        "background_assets": asset_urls,
        "background_match_mode": recommendation["mode"],
        "background_match_reason": recommendation["reason"],
        "background_match_tags": list(recommendation["matched_tags"]),
        "subtitle_enabled": bool(subtitle_enabled),
        "subtitle_style": resolved_subtitle_style["id"],
        "subtitle_style_name": resolved_subtitle_style["label"],
        "subtitle_url": None,
        "subtitle_segments": [],
        "bgm_url": None,
        "audio_mix_mode": None,
        **audio_mix_settings,
        "horse_profile": horse_profile or {},
        "generation_mode": "ffmpeg-queued",
        "batch_id": batch_id,
        "attempt": attempt,
        "scene_count": 0,
    }


def _ffmpeg_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace(":", "\\:")


def _find_font_path() -> Path:
    candidates = [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _chunk_text(text: str, limit: int = 18, max_lines: int = 3) -> str:
    stripped = "".join(text.split())
    if not stripped:
        return ""
    lines = [stripped[index : index + limit] for index in range(0, len(stripped), limit)]
    return "\n".join(lines[:max_lines])


def _write_text_artifact(task_id: str, suffix: str, text: str, *, limit: int = 18, max_lines: int = 3) -> Path:
    ensure_generated_dirs()
    path = TEXT_DIR / f"{task_id}_{suffix}.txt"
    path.write_text(_chunk_text(text, limit=limit, max_lines=max_lines), encoding="utf-8")
    return path


def _resolve_generated_file(url: str | None) -> Path | None:
    if not url or not url.startswith("/generated/"):
        return None
    return SERVER_DIR / Path(url.lstrip("/"))


def _run_ffmpeg(args: list[str]) -> None:
    process = subprocess.run(args, check=False, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if process.returncode != 0:
        error_text = process.stderr.strip() or process.stdout.strip() or "Unknown ffmpeg error"
        raise RuntimeError(error_text)


def _seconds_to_srt_timestamp(value: float) -> str:
    total_milliseconds = max(0, int(round(value * 1000)))
    milliseconds = total_milliseconds % 1000
    total_seconds = total_milliseconds // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def build_subtitle_segments(shots: list[dict[str, Any]], duration_seconds: float) -> list[dict[str, Any]]:
    usable_shots = [shot for shot in shots if str(shot.get("subtitle", "")).strip()]
    if not usable_shots:
        return []

    segment_duration = max(duration_seconds / max(1, len(usable_shots)), 1.5)
    segments: list[dict[str, Any]] = []
    for index, shot in enumerate(usable_shots):
        start_seconds = round(index * segment_duration, 2)
        if index == len(usable_shots) - 1:
            end_seconds = round(duration_seconds, 2)
        else:
            end_seconds = round(min(duration_seconds, (index + 1) * segment_duration - 0.08), 2)
        if end_seconds <= start_seconds:
            end_seconds = round(min(duration_seconds, start_seconds + 1.2), 2)
        segments.append(
            {
                "scene": int(shot.get("scene", index + 1)),
                "text": str(shot.get("subtitle", "")).strip(),
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
            }
        )
    return segments


def _write_subtitle_artifact(task_id: str, segments: list[dict[str, Any]]) -> str | None:
    if not segments:
        return None

    ensure_generated_dirs()
    subtitle_path = SUBTITLE_DIR / f"{task_id}.srt"
    lines: list[str] = []
    for index, segment in enumerate(segments, start=1):
        lines.extend(
            [
                str(index),
                f"{_seconds_to_srt_timestamp(float(segment['start_seconds']))} --> {_seconds_to_srt_timestamp(float(segment['end_seconds']))}",
                str(segment["text"]),
                "",
            ]
        )
    subtitle_path.write_text("\n".join(lines), encoding="utf-8")
    return f"/generated/subtitles/{subtitle_path.name}"


def _resolve_music_style(music: str | None) -> str:
    normalized = str(music or "").strip().lower()
    if normalized in {"epic", "calm", "traditional"}:
        return normalized
    return "epic"


def _procedural_music_sample(style: str, t: float) -> float:
    if style == "calm":
        notes = [174.61, 220.0, 261.63, 329.63]
        note = notes[int(t / 4.5) % len(notes)]
        pad = math.sin(2 * math.pi * note * t) + 0.6 * math.sin(2 * math.pi * (note * 0.5) * t + 0.4)
        shimmer = math.sin(2 * math.pi * (note * 2.0) * t + 1.2) * (0.5 + 0.5 * math.sin(2 * math.pi * 0.12 * t))
        return 0.09 * pad + 0.035 * shimmer

    if style == "traditional":
        notes = [196.0, 220.0, 293.66, 329.63, 392.0]
        note = notes[int(t / 1.45) % len(notes)]
        drone_note = notes[int(t / 5.2) % len(notes)] * 0.5
        pluck_envelope = math.exp(-((t % 1.45) * 3.8))
        drone = math.sin(2 * math.pi * drone_note * t + 0.3)
        melody = (math.sin(2 * math.pi * note * t) + 0.32 * math.sin(2 * math.pi * (note * 2.0) * t)) * pluck_envelope
        return 0.085 * drone + 0.11 * melody

    notes = [55.0, 69.3, 82.41, 98.0]
    note = notes[int(t / 2.4) % len(notes)]
    drone = (
        math.sin(2 * math.pi * (note * 0.5) * t)
        + 0.58 * math.sin(2 * math.pi * note * t)
        + 0.25 * math.sin(2 * math.pi * (note * 1.5) * t)
    )
    pulse = (0.4 + 0.6 * (math.sin(2 * math.pi * 0.72 * t) ** 2)) * math.sin(2 * math.pi * (note * 2.0) * t)
    return 0.12 * drone + 0.05 * pulse


def build_music_artifact(track_key: str, music: str, duration_seconds: float) -> dict[str, Any]:
    ensure_generated_dirs()
    style = _resolve_music_style(music)
    artifact_id = hashlib.md5(f"{track_key}:{style}:{round(duration_seconds, 2)}".encode("utf-8")).hexdigest()[:16]
    music_path = MUSIC_DIR / f"{artifact_id}_{style}.wav"
    if not music_path.exists():
        duration = max(3.0, float(duration_seconds))
        sample_count = int(AUDIO_SAMPLE_RATE * duration)
        fade_out_start = max(0.8, duration - 1.2)
        pcm = bytearray()
        for index in range(sample_count):
            t = index / AUDIO_SAMPLE_RATE
            fade_in = min(1.0, t / 0.8)
            fade_out = 1.0 if t <= fade_out_start else max(0.0, (duration - t) / max(0.35, duration - fade_out_start))
            envelope = fade_in * fade_out
            left = max(-1.0, min(1.0, _procedural_music_sample(style, t) * envelope))
            right = max(-1.0, min(1.0, _procedural_music_sample(style, t + 0.008) * envelope))
            pcm.extend(struct.pack("<hh", int(left * 32767), int(right * 32767)))

        with wave.open(str(music_path), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(AUDIO_SAMPLE_RATE)
            stream.writeframes(bytes(pcm))

    return {
        "bgm_url": f"/generated/music/{music_path.name}",
        "duration_seconds": round(max(3.0, float(duration_seconds)), 2),
        "generation_mode": "procedural",
        "style": style,
    }


def build_audio_filter_parts(
    *,
    duration_seconds: float,
    narration_input_index: int | None,
    bgm_input_index: int | None,
    bgm_volume: float | None = None,
    ducking_threshold: float | None = None,
    ducking_ratio: float | None = None,
    ducking_attack_ms: int | None = None,
    ducking_release_ms: int | None = None,
) -> tuple[list[str], str]:
    parts: list[str] = []
    has_narration = narration_input_index is not None
    has_bgm = bgm_input_index is not None
    mix_settings = _normalize_audio_mix_settings(
        bgm_volume=bgm_volume,
        ducking_threshold=ducking_threshold,
        ducking_ratio=ducking_ratio,
        ducking_attack_ms=ducking_attack_ms,
        ducking_release_ms=ducking_release_ms,
    )

    if has_bgm:
        parts.append(
            f"[{bgm_input_index}:a]atrim=duration={duration_seconds:.2f},asetpts=PTS-STARTPTS,aresample=44100,volume={mix_settings['bgm_volume']:.2f}[bgm]"
        )
    if has_narration:
        parts.append(
            f"[{narration_input_index}:a]atrim=duration={duration_seconds:.2f},asetpts=PTS-STARTPTS,aresample=44100,volume=1.0[narr]"
        )

    if has_bgm and has_narration:
        parts.extend(
            [
                "[bgm][narr]"
                f"sidechaincompress=threshold={mix_settings['ducking_threshold']:.3f}:ratio={mix_settings['ducking_ratio']:.2f}:"
                f"attack={mix_settings['ducking_attack_ms']}:release={mix_settings['ducking_release_ms']}:makeup=1[bgmduck]",
                "[bgmduck][narr]amix=inputs=2:weights='0.58 1.0':normalize=0:duration=longest[audioout]",
            ]
        )
        return parts, "narration+bgm-ducked"
    if has_narration:
        parts.append("[narr]anull[audioout]")
        return parts, "narration-only"
    if has_bgm:
        parts.append("[bgm]anull[audioout]")
        return parts, "bgm-only"

    raise RuntimeError("No audio inputs available for video render")


def _build_drawtext_filter(
    *,
    font_path: Path,
    textfile: Path,
    font_size: int,
    x: str,
    y: str,
    font_color: str,
    box: bool = False,
    box_color: str = "black@0.35",
    box_border: int = 24,
    line_spacing: int = 8,
    border_width: float = 0.0,
    border_color: str = "black@0.0",
    shadow_color: str = "black@0.55",
    shadow_x: int = 2,
    shadow_y: int = 2,
) -> str:
    parts = [
        f"drawtext=fontfile='{_ffmpeg_filter_path(font_path)}'",
        f"textfile='{_ffmpeg_filter_path(textfile)}'",
        "reload=0",
        f"fontcolor={font_color}",
        f"fontsize={font_size}",
        f"line_spacing={line_spacing}",
        f"x={x}",
        f"y={y}",
        f"shadowcolor={shadow_color}",
        f"shadowx={shadow_x}",
        f"shadowy={shadow_y}",
    ]
    if border_width > 0:
        parts.extend([f"borderw={border_width}", f"bordercolor={border_color}"])
    if box:
        parts.extend(["box=1", f"boxcolor={box_color}", f"boxborderw={box_border}"])
    return ":".join(parts)


def _default_scene_segments(task: VideoTask) -> list[dict[str, Any]]:
    script_payload = dict(task.script_payload or {})
    segments = [
        {"scene": 1, "visual": str(script_payload.get("opening", "")).strip(), "subtitle": str(script_payload.get("opening", "")).strip()},
        {"scene": 2, "visual": str(script_payload.get("body", "")).strip(), "subtitle": str(script_payload.get("body", "")).strip()},
        {"scene": 3, "visual": str(script_payload.get("closing", "")).strip(), "subtitle": str(script_payload.get("closing", "")).strip()},
    ]
    filtered = [item for item in segments if item["visual"] or item["subtitle"]]
    if filtered:
        return filtered
    return [{"scene": 1, "visual": task.horse_name, "subtitle": task.custom_text or task.horse_name}]


def _resolve_scene_segments(task: VideoTask) -> list[dict[str, Any]]:
    raw_shots = list((task.script_payload or {}).get("shots") or [])
    if not raw_shots:
        return _default_scene_segments(task)
    return [
        {
            "scene": int(shot.get("scene", index + 1)),
            "visual": str(shot.get("visual", "")).strip(),
            "subtitle": str(shot.get("subtitle", "")).strip(),
        }
        for index, shot in enumerate(raw_shots)
    ]


def _build_subtitle_overlay_filters(
    *,
    font_path: Path,
    subtitle_file: Path,
    subtitle_style_id: str,
    template_id: str,
    subtitle_enabled: bool,
    subtitle_text: str,
) -> list[str]:
    if not subtitle_enabled or not subtitle_text.strip():
        return []

    subtitle_style = _resolve_subtitle_style(subtitle_style_id, template_id)
    return [
        _build_drawtext_filter(
            font_path=font_path,
            textfile=subtitle_file,
            font_size=int(subtitle_style["font_size"]),
            x=str(subtitle_style["x"]),
            y=str(subtitle_style["y"]),
            font_color=str(subtitle_style["font_color"]),
            box=True,
            box_color=str(subtitle_style["box_color"]),
            box_border=int(subtitle_style["box_border"]),
            line_spacing=int(subtitle_style["line_spacing"]),
            border_width=float(subtitle_style["border_width"]),
            border_color=str(subtitle_style["border_color"]),
            shadow_color=str(subtitle_style["shadow_color"]),
            shadow_x=int(subtitle_style["shadow_x"]),
            shadow_y=int(subtitle_style["shadow_y"]),
        )
    ]


def _build_scene_filter_chain(
    *,
    input_index: int,
    task: VideoTask,
    scene: dict[str, Any],
    scene_index: int,
    total_scenes: int,
    template_id: str,
    background_pack_name: str,
    input_duration: float,
    subtitle_style_id: str,
    subtitle_enabled: bool,
) -> str:
    font_path = _find_font_path()
    preset = _resolve_scene_template(template_id)
    horse_file = _write_text_artifact(task.id, f"horse_{scene_index}", task.horse_name, limit=10, max_lines=2)
    title_file = _write_text_artifact(
        task.id,
        f"title_{scene_index}",
        str((task.script_payload or {}).get("title") or task.horse_name),
        limit=16,
        max_lines=2,
    )
    visual_file = _write_text_artifact(task.id, f"visual_{scene_index}", scene.get("visual", ""), limit=16, max_lines=3)
    subtitle_file = _write_text_artifact(task.id, f"subtitle_{scene_index}", scene.get("subtitle", ""), limit=20, max_lines=3)
    counter_file = _write_text_artifact(task.id, f"counter_{scene_index}", f"{scene_index + 1:02d}/{total_scenes:02d}", limit=12, max_lines=1)
    footer_file = _write_text_artifact(task.id, f"footer_{scene_index}", "百骑谱 · AI 视频工厂", limit=18, max_lines=1)
    meta_file = _write_text_artifact(
        task.id,
        f"meta_{scene_index}",
        f"{task.visual_style} · {task.script_style} · {task.duration}s",
        limit=22,
        max_lines=1,
    )
    background_file = _write_text_artifact(task.id, f"background_{scene_index}", f"素材库：{background_pack_name}", limit=20, max_lines=1)
    subtitle_filters = _build_subtitle_overlay_filters(
        font_path=font_path,
        subtitle_file=subtitle_file,
        subtitle_style_id=subtitle_style_id,
        template_id=template_id,
        subtitle_enabled=subtitle_enabled,
        subtitle_text=scene.get("subtitle", ""),
    )

    filters = [f"[{input_index}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},format=yuv420p"]

    if template_id == "battle":
        filters.extend(
            [
                f"drawbox=x=48:y=48:w=1184:h=624:color={preset['panel']}:t=fill",
                f"drawbox=x=62:y=60+18*sin(t*1.3):w=440:h=12:color={preset['accent']}@0.95:t=fill",
                f"drawbox=x=1048:y=54:w=150:h=150:color={preset['accent']}@0.14:t=fill",
                f"drawbox=x=1048:y=54:w=150:h=150:color={preset['frame']}:t=4",
                _build_drawtext_filter(font_path=font_path, textfile=counter_file, font_size=34, x="1078", y="104", font_color=preset["text"]),
                _build_drawtext_filter(font_path=font_path, textfile=horse_file, font_size=32, x="86", y="86", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=visual_file, font_size=58, x="86", y="206", font_color=preset["text"]),
                *subtitle_filters,
                _build_drawtext_filter(font_path=font_path, textfile=title_file, font_size=26, x="88", y="152", font_color=preset["accent"]),
                _build_drawtext_filter(font_path=font_path, textfile=footer_file, font_size=24, x="88", y="612", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=background_file, font_size=22, x="88", y="648", font_color=preset["muted"]),
            ]
        )
    elif template_id == "legend":
        filters.extend(
            [
                f"drawbox=x=78:y=66:w=1124:h=544:color={preset['panel']}:t=fill",
                f"drawbox=x=78:y=66:w=1124:h=544:color={preset['frame']}:t=4",
                f"drawbox=x=112:y=102:w=1056:h=476:color={preset['accent']}@0.08:t=fill",
                _build_drawtext_filter(font_path=font_path, textfile=title_file, font_size=28, x="(w-text_w)/2", y="112", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=visual_file, font_size=60, x="(w-text_w)/2", y="240", font_color=preset["text"]),
                _build_drawtext_filter(font_path=font_path, textfile=horse_file, font_size=34, x="110", y="526", font_color=preset["accent"]),
                *subtitle_filters,
                _build_drawtext_filter(font_path=font_path, textfile=counter_file, font_size=28, x="1030", y="110", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=footer_file, font_size=22, x="910", y="560", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=background_file, font_size=22, x="110", y="122", font_color=preset["muted"]),
            ]
        )
    else:
        filters.extend(
            [
                f"drawbox=x=54:y=54:w=1172:h=612:color={preset['panel']}:t=fill",
                f"drawbox=x=54:y=54:w=1172:h=612:color={preset['frame']}:t=4",
                f"drawbox=x=86:y=86:w=10:h=506:color={preset['accent']}@0.95:t=fill",
                f"drawbox=x=102:y=500:w=1060:h=102:color=black@0.28:t=fill",
                _build_drawtext_filter(font_path=font_path, textfile=horse_file, font_size=34, x="122", y="90", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=title_file, font_size=28, x="122", y="150", font_color=preset["accent"]),
                _build_drawtext_filter(font_path=font_path, textfile=visual_file, font_size=58, x="122", y="236", font_color=preset["text"]),
                *subtitle_filters,
                _build_drawtext_filter(font_path=font_path, textfile=counter_file, font_size=30, x="1068", y="88", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=meta_file, font_size=24, x="124", y="190", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=footer_file, font_size=22, x="124", y="612", font_color=preset["muted"]),
                _build_drawtext_filter(font_path=font_path, textfile=background_file, font_size=22, x="124", y="646", font_color=preset["muted"]),
            ]
        )

    filters.extend([f"trim=duration={input_duration:.2f}", "setsar=1", "fps=30", "setpts=PTS-STARTPTS"])
    return ",".join(filters) + f"[scene{scene_index}]"


def _render_video_assets(task: VideoTask) -> dict[str, Any]:
    ensure_generated_dirs()
    compose_payload = dict(task.compose_payload or {})
    tts_payload = dict(task.tts_payload or {})
    shots = _resolve_scene_segments(task)

    duration_seconds = max(
        task.duration,
        int(math.ceil(float(tts_payload.get("duration_seconds") or 0))) + (1 if task.narration else 0),
    )
    scene_count = max(1, len(shots))
    template_id = _resolve_scene_template_id(compose_payload.get("scene_template"))
    transition = _resolve_transition(compose_payload.get("transition"), template_id)
    subtitle_enabled = bool(compose_payload.get("subtitle_enabled", True))
    subtitle_style = _resolve_subtitle_style(compose_payload.get("subtitle_style"), template_id)
    audio_mix_settings = _normalize_audio_mix_settings(
        bgm_volume=compose_payload.get("bgm_volume"),
        ducking_threshold=compose_payload.get("ducking_threshold"),
        ducking_ratio=compose_payload.get("ducking_ratio"),
        ducking_attack_ms=compose_payload.get("ducking_attack_ms"),
        ducking_release_ms=compose_payload.get("ducking_release_ms"),
    )
    horse_profile = compose_payload.get("horse_profile") if isinstance(compose_payload.get("horse_profile"), dict) else {}
    requested_pack = compose_payload.get("background_pack") if compose_payload.get("background_mode") == "manual" else None
    background_pack, recommendation = recommend_background_pack(requested_pack, template_id, horse_profile=horse_profile)
    background_assets = resolve_background_assets(background_pack["id"], template_id, scene_count)

    scene_duration = max(3.0, duration_seconds / scene_count)
    transition_duration = 0.70 if scene_count > 1 else 0.0
    input_duration = round(scene_duration + transition_duration, 2)
    subtitle_segments = build_subtitle_segments(shots, duration_seconds) if subtitle_enabled else []
    subtitle_url = _write_subtitle_artifact(task.id, subtitle_segments)
    bgm_payload = build_music_artifact(task.id, task.music, duration_seconds)

    video_path = VIDEO_DIR / f"{task.id}.mp4"
    thumbnail_path = THUMBNAIL_DIR / f"{task.id}.png"

    command = [FFMPEG_BIN, "-y"]
    for asset in background_assets:
        asset_path = Path(str(asset["file_path"]))
        command.extend(
            [
                "-loop",
                "1",
                "-framerate",
                str(FPS),
                "-t",
                f"{input_duration:.2f}",
                "-i",
                str(asset_path),
            ]
        )

    next_input_index = scene_count
    narration_input_index: int | None = None
    audio_path = _resolve_generated_file(tts_payload.get("audio_url"))
    if task.narration and audio_path and audio_path.exists():
        command.extend(["-i", str(audio_path)])
        narration_input_index = next_input_index
        next_input_index += 1

    bgm_input_index: int | None = None
    bgm_path = _resolve_generated_file(bgm_payload.get("bgm_url"))
    if bgm_path and bgm_path.exists():
        command.extend(["-i", str(bgm_path)])
        bgm_input_index = next_input_index
        next_input_index += 1

    if narration_input_index is None and bgm_input_index is None:
        command.extend(["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration_seconds:.2f}"])
        narration_input_index = next_input_index

    filter_parts = [
        _build_scene_filter_chain(
            input_index=index,
            task=task,
            scene=shots[index],
            scene_index=index,
            total_scenes=scene_count,
            template_id=template_id,
            background_pack_name=str(background_pack["name"]),
            input_duration=input_duration,
            subtitle_style_id=subtitle_style["id"],
            subtitle_enabled=subtitle_enabled,
        )
        for index in range(scene_count)
    ]

    if scene_count == 1:
        filter_parts.append(f"[scene0]trim=duration={duration_seconds:.2f},setpts=PTS-STARTPTS[videoout]")
    else:
        filter_parts.append(
            f"[scene0][scene1]xfade=transition={transition}:duration={transition_duration:.2f}:offset={scene_duration:.2f}[mix1]"
        )
        for index in range(2, scene_count):
            offset = scene_duration * index
            filter_parts.append(
                f"[mix{index - 1}][scene{index}]xfade=transition={transition}:duration={transition_duration:.2f}:offset={offset:.2f}[mix{index}]"
            )
        filter_parts.append(
            f"[mix{scene_count - 1}]trim=duration={duration_seconds:.2f},setpts=PTS-STARTPTS[videoout]"
        )

    audio_filter_parts, audio_mix_mode = build_audio_filter_parts(
        duration_seconds=duration_seconds,
        narration_input_index=narration_input_index,
        bgm_input_index=bgm_input_index,
        **audio_mix_settings,
    )
    filter_parts.extend(audio_filter_parts)

    command.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[videoout]",
            "-map",
            "[audioout]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-shortest",
            str(video_path),
        ]
    )

    _run_ffmpeg(command)

    screenshot_at = f"{min(max(duration_seconds * 0.2, 0.20), 1.50):.2f}"
    _run_ffmpeg(
        [
            FFMPEG_BIN,
            "-y",
            "-ss",
            screenshot_at,
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(thumbnail_path),
        ]
    )

    compose_payload.update(
        {
            "video_url": f"/generated/videos/{video_path.name}",
            "thumbnail_url": f"/generated/thumbnails/{thumbnail_path.name}",
            "cover_url": f"/generated/thumbnails/{thumbnail_path.name}",
            "duration": duration_seconds,
            "transition": transition,
            "scene_template": template_id,
            "scene_template_label": _resolve_scene_template(template_id)["label"],
            "background_mode": compose_payload.get("background_mode") or "auto",
            "background_pack": background_pack["id"],
            "background_pack_name": background_pack["name"],
            "background_preview_url": background_pack["preview_url"],
            "background_assets": [str(asset["file_url"]) for asset in background_assets],
            "background_match_mode": recommendation["mode"],
            "background_match_reason": recommendation["reason"],
            "background_match_tags": list(recommendation["matched_tags"]),
            "subtitle_enabled": subtitle_enabled,
            "subtitle_style": subtitle_style["id"],
            "subtitle_style_name": subtitle_style["label"],
            "subtitle_url": subtitle_url,
            "subtitle_segments": subtitle_segments,
            "bgm_url": bgm_payload.get("bgm_url"),
            "audio_mix_mode": audio_mix_mode,
            **audio_mix_settings,
            "horse_profile": horse_profile,
            "scene_count": scene_count,
            "generation_mode": "ffmpeg-multiscene",
        }
    )
    return compose_payload


def _set_task_state(
    task_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    compose_payload: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    session = SessionLocal()
    try:
        task = session.query(VideoTask).filter(VideoTask.id == task_id).first()
        if not task:
            return
        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if compose_payload is not None:
            task.compose_payload = compose_payload
        task.error_message = error_message
        task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(task)
        session.commit()
    finally:
        session.close()


def process_video_task(task_id: str) -> None:
    try:
        _set_task_state(task_id, status="processing", progress=12)

        session = SessionLocal()
        try:
            task = session.query(VideoTask).filter(VideoTask.id == task_id).first()
            if not task:
                return
            queued_payload = dict(task.compose_payload or {})
            queued_payload["scene_count"] = len(_resolve_scene_segments(task))
        finally:
            session.close()

        _set_task_state(task_id, progress=42, compose_payload=queued_payload)

        session = SessionLocal()
        try:
            task = session.query(VideoTask).filter(VideoTask.id == task_id).first()
            if not task:
                return
            completed_payload = _render_video_assets(task)
        finally:
            session.close()

        _set_task_state(task_id, status="completed", progress=100, compose_payload=completed_payload, error_message=None)
    except Exception as exc:
        _set_task_state(task_id, status="failed", progress=100, error_message=str(exc))
    finally:
        with _QUEUE_LOCK:
            _ENQUEUED_TASKS.discard(task_id)


def enqueue_video_task(task_id: str) -> None:
    with _QUEUE_LOCK:
        if task_id in _ENQUEUED_TASKS:
            return
        _ENQUEUED_TASKS.add(task_id)
    VIDEO_QUEUE_EXECUTOR.submit(process_video_task, task_id)


def advance_video_task(task: VideoTask) -> VideoTask:
    if task.status in {"queued", "processing"}:
        enqueue_video_task(task.id)
    return task


def serialize_video_task(task: VideoTask) -> dict[str, Any]:
    compose_payload = dict(task.compose_payload or {})
    tts_payload = dict(task.tts_payload or {})
    return {
        "task_id": task.id,
        "horse_id": task.horse_id,
        "horse_name": task.horse_name,
        "status": task.status,
        "progress": task.progress,
        "style": task.visual_style,
        "script_style": task.script_style,
        "duration": task.duration,
        "music": task.music,
        "narration": task.narration,
        "voice": task.voice,
        "scene_template": compose_payload.get("scene_template"),
        "transition": compose_payload.get("transition"),
        "background_mode": compose_payload.get("background_mode"),
        "background_pack": compose_payload.get("background_pack"),
        "background_pack_name": compose_payload.get("background_pack_name"),
        "background_preview_url": compose_payload.get("background_preview_url"),
        "background_assets": list(compose_payload.get("background_assets") or []),
        "background_match_mode": compose_payload.get("background_match_mode"),
        "background_match_reason": compose_payload.get("background_match_reason"),
        "background_match_tags": list(compose_payload.get("background_match_tags") or []),
        "subtitle_enabled": compose_payload.get("subtitle_enabled"),
        "subtitle_style": compose_payload.get("subtitle_style"),
        "subtitle_style_name": compose_payload.get("subtitle_style_name"),
        "generation_mode": compose_payload.get("generation_mode"),
        "batch_id": compose_payload.get("batch_id"),
        "attempt": int(compose_payload.get("attempt") or 1),
        "script": task.script_payload or None,
        "audio_url": tts_payload.get("audio_url"),
        "bgm_url": compose_payload.get("bgm_url"),
        "audio_mix_mode": compose_payload.get("audio_mix_mode"),
        "bgm_volume": compose_payload.get("bgm_volume"),
        "ducking_threshold": compose_payload.get("ducking_threshold"),
        "ducking_ratio": compose_payload.get("ducking_ratio"),
        "ducking_attack_ms": compose_payload.get("ducking_attack_ms"),
        "ducking_release_ms": compose_payload.get("ducking_release_ms"),
        "subtitle_url": compose_payload.get("subtitle_url"),
        "subtitle_segments": list(compose_payload.get("subtitle_segments") or []),
        "video_url": compose_payload.get("video_url"),
        "thumbnail_url": compose_payload.get("thumbnail_url"),
        "cover_url": compose_payload.get("cover_url"),
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "estimated_seconds": task.estimated_seconds,
        "error_message": task.error_message,
    }
