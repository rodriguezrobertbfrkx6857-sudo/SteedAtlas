import hashlib
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(
    os.environ.get(
        "STEEDATLAS_ROOT", next((str(p) for p in Path(__file__).resolve().parents if (p / ".git").exists()), ".")
    )
).resolve()
STORE = ROOT / "runtime/media"
STORE.mkdir(parents=True, exist_ok=True)
FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE_BIN", "ffprobe")


def run(args, timeout=180, cwd=None):
    result = subprocess.run(args, capture_output=True, timeout=timeout, cwd=cwd)
    if result.returncode:
        # Full stderr stays in private diagnostics; API exposes only an error class.
        log = STORE / "last-ffmpeg-error.txt"
        log.write_bytes(result.stderr[-16000:])
        raise ValueError("MEDIA_PROCESS_FAILED")
    return result.stdout


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def probe(path):
    return json.loads(
        run(
            [
                FFPROBE,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            timeout=30,
        )
    )


def verify(path, expected_duration=None):
    p = Path(path)
    metadata = probe(p)
    video = next((s for s in metadata["streams"] if s["codec_type"] == "video"), None)
    if not video:
        raise ValueError("NO_VIDEO_STREAM")
    duration = float(metadata["format"].get("duration", 0))
    if expected_duration and abs(duration - expected_duration) > 0.25:
        raise ValueError("DURATION_MISMATCH")
    run([FFMPEG, "-v", "error", "-protocol_whitelist", "file,pipe", "-i", str(p), "-f", "null", "-"], timeout=180)
    return {
        "sha256": sha(p),
        "bytes": p.stat().st_size,
        "duration": duration,
        "width": video["width"],
        "height": video["height"],
        "fps": video["r_frame_rate"],
        "audio_streams": sum(s["codec_type"] == "audio" for s in metadata["streams"]),
        "decoded": True,
    }


def validate_upload(path):
    p = Path(path)
    try:
        with Image.open(p) as image:
            if image.width * image.height > 24_000_000 or image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("IMAGE_LIMIT")
            image.verify()
        return {"media_type": "image", "duration": None}
    except (OSError, SyntaxError):
        pass
    with p.open("rb") as source:
        header = source.read(64)
    # Reject playlists, manifests, scripts and URL indirection before invoking a decoder.
    container = (
        header[4:8] == b"ftyp"
        or header.startswith((b"ID3", b"OggS", b"fLaC"))
        or (header.startswith(b"RIFF") and header[8:12] == b"WAVE")
        or (len(header) > 1 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0)
    )
    if not container:
        raise ValueError("UNSUPPORTED_CONTAINER_SIGNATURE")
    data = probe(p)
    duration = float(data.get("format", {}).get("duration", 0))
    if not 0 < duration <= 180:
        raise ValueError("MEDIA_DURATION_LIMIT")
    if any(s.get("width", 0) * s.get("height", 0) > 8_294_400 for s in data["streams"]):
        raise ValueError("MEDIA_RESOLUTION_LIMIT")
    run([FFMPEG, "-v", "error", "-protocol_whitelist", "file,pipe", "-i", str(p), "-t", "180", "-f", "null", "-"])
    return {
        "media_type": "video" if any(s["codec_type"] == "video" for s in data["streams"]) else "audio",
        "duration": duration,
    }


def safe_path(value):
    p = (STORE / value).resolve()
    if not p.is_relative_to(STORE.resolve()) or not p.is_file():
        raise ValueError("MISSING_OR_UNSAFE_ARTIFACT")
    return p


def artifact(path, **extra):
    p = Path(path)
    return {"storage_key": p.relative_to(STORE).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size, **extra}


def valid_artifact(output):
    try:
        p = safe_path(output["storage_key"])
        return sha(p) == output["sha256"] and (not output.get("decoded") or verify(p)["decoded"])
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        return False


def template(path, index=0):
    """Original programmatically drawn museum plates; no downloaded media."""
    image = Image.new("RGB", (1280, 720), ["#e8dfce", "#d6e0db", "#dadbe4"][index % 3])
    d = ImageDraw.Draw(image)
    for x in range(70, 1280, 120):
        d.line((x, 0, x, 720), fill="#c8c3b8", width=1)
    d.ellipse((510, 130, 1080, 700), fill=["#b5a486", "#a8b8ac", "#b7acbd"][index % 3])
    # Deliberately stylized horse silhouette, an editorial illustration rather than a historical reconstruction.
    d.polygon(
        [
            (590, 360),
            (820, 355),
            (870, 230),
            (860, 165),
            (895, 195),
            (935, 185),
            (980, 255),
            (940, 282),
            (915, 270),
            (895, 395),
            (845, 430),
            (830, 585),
            (808, 585),
            (800, 440),
            (700, 435),
            (650, 585),
            (625, 585),
            (658, 420),
            (590, 415),
        ],
        fill="#713b2c",
    )
    d.line([(595, 370), (545, 395), (515, 470)], fill="#713b2c", width=20)
    d.line([(80, 620), (1200, 620)], fill="#837b6a", width=2)
    image.save(path)


def font():
    candidates = [
        os.environ.get("STEEDATLAS_FONT", ""),
        "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    p = next((Path(x) for x in candidates if x and Path(x).is_file()), None)
    if not p:
        raise ValueError("FONT_REQUIRED")
    target = STORE / "local-font.ttf"
    if not target.exists():
        shutil.copyfile(p, target)
    return target


def filter_path(path):
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def segment(params, output_path):
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    scene, project = params["scene"], params["project"]
    duration = scene["duration_ticks"] / project["fps_num"]
    media = params.get("asset")
    if media:
        input_path = safe_path(media["storage_key"])
        if sha(input_path) != media["sha256"]:
            raise ValueError("ASSET_HASH_MISMATCH")
    else:
        input_path = p.with_suffix(".png")
        template(input_path, params["index"])
    image_input = not media or media["media_type"] == "image"
    args = [FFMPEG, "-nostdin", "-y", "-v", "error"]
    args += ["-loop", "1"] if image_input else ["-stream_loop", "-1"]
    args += ["-i", str(input_path)]
    w, h = project["width"], project["height"]
    textfile = p.with_suffix(".txt")
    labels = {
        "CREATIVE": "艺术演绎",
        "LITERARY": "文学叙事",
        "ATTESTED": "史料记载",
        "FOLKLORE": "民间传说",
        "EDITORIAL": "编辑整理",
        "DISPUTED": "存在争议",
        "SOURCE_ATTRIBUTED": "文献引文·机器核对·未人工审核",
        "LITERARY_ATTRIBUTED": "文学引文·机器核对·未人工审核",
    }
    textfile.write_text(scene["text"], encoding="utf-8")
    f = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={project['fps_num']}"
    if image_input:
        f += f",zoompan=z='min(zoom+0.0003,1.08)':d=1:s={w}x{h}:fps={project['fps_num']}"
    font()
    if params.get("citations"):
        c = params["citations"][0]
        # Credit the exact edition in the actual video, not only in the API payload.
        credit = p.with_suffix(".credit.txt")
        credit.write_text(
            f"{c['source_title']} · Wikisource {c.get('upstream_revision') or c['source_revision']} · {c.get('license', '')}\n維基文庫貢獻者 · 節錄原文 · 詳見專案引文連結",
            encoding="utf-8",
        )
        f += f",drawtext=fontfile='local-font.ttf':textfile='{credit.relative_to(STORE).as_posix()}':fontcolor=white:fontsize=18:x=24:y=24:box=1:boxcolor=black@0.7"
    f += f",drawbox=x=0:y=ih-160:w=iw:h=160:color=black@0.68:t=fill,drawtext=fontfile='local-font.ttf':text='{labels[scene['label']]}':fontcolor=white:fontsize=20:x=48:y=h-142"
    lines = textwrap.wrap(scene["text"], max(12, w // 40)) or [""]
    pages = [lines[i : i + 2] for i in range(0, len(lines), 2)]
    for page_index, page_lines in enumerate(pages):
        for line_index, line in enumerate(page_lines):
            line_file = p.with_suffix(f".{page_index}.{line_index}.txt")
            line_file.write_text(line, encoding="utf-8")
            start, end = page_index * duration / len(pages), (page_index + 1) * duration / len(pages)
            f += f",drawtext=fontfile='local-font.ttf':textfile='{line_file.relative_to(STORE).as_posix()}':fontcolor=white:fontsize={max(24, w // 46)}:x=48:y=h-{92 - line_index * 42}:enable='gte(t,{start})*lt(t,{end})'"
    args += [
        "-vf",
        f,
        "-t",
        str(duration),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "2",
        str(p),
    ]
    run(args, cwd=STORE)
    return artifact(p, **{k: v for k, v in verify(p, duration).items() if k not in {"sha256", "bytes"}})


def srt(project):
    def stamp(tick):
        ms = round(tick * 1000 / project["fps_num"])
        sec, ms = divmod(ms, 1000)
        minute, sec = divmod(sec, 60)
        hour, minute = divmod(minute, 60)
        return f"{hour:02}:{minute:02}:{sec:02},{ms:03}"

    cursor = 0
    entries = []
    for n, scene in enumerate(project["scenes"], 1):
        end = cursor + scene["duration_ticks"]
        entries.append(f"{n}\n{stamp(cursor)} --> {stamp(end)}\n[{scene['label']}] {scene['text']}\n")
        cursor = end
    return "\n".join(entries)


def compose(project, inputs, audio, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    listing = output.with_suffix(".concat.txt")
    # All paths are application-owned, never supplied in an FFmpeg expression by users.
    listing.write_text(
        "\n".join("file '" + safe_path(x["storage_key"]).as_posix() + "'" for x in inputs), encoding="utf-8"
    )
    duration = sum(s["duration_ticks"] for s in project["scenes"]) / project["fps_num"]
    args = [FFMPEG, "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing)]
    for a in audio:
        path = safe_path(a["storage_key"])
        if sha(path) != a["sha256"]:
            raise ValueError("AUDIO_HASH_MISMATCH")
        args += ["-i", str(path)]
    if audio:
        filters = ";".join(
            f"[{i + 1}:a]volume={project['audio_gain']},afade=t=in:d={project['audio_fade_seconds']}[a{i}]"
            for i in range(len(audio))
        )
        filters += (
            ";" + "".join(f"[a{i}]" for i in range(len(audio))) + f"amix=inputs={len(audio)}:normalize=0,apad[mix]"
        )
        args += ["-filter_complex", filters, "-map", "0:v", "-map", "[mix]", "-c:a", "aac"]
    args += ["-c:v", "copy", "-t", str(duration), "-movflags", "+faststart", str(output)]
    run(args)
    return artifact(output, **{k: v for k, v in verify(output, duration).items() if k not in {"sha256", "bytes"}})
