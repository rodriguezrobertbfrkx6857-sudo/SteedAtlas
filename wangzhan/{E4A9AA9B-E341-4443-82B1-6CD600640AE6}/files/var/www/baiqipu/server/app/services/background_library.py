from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parents[2]
ASSET_ROOT = SERVER_DIR / "assets"
BACKGROUND_LIBRARY_DIR = ASSET_ROOT / "video_backgrounds"
BACKGROUND_MANIFEST_PATH = BACKGROUND_LIBRARY_DIR / "manifest.json"
BACKGROUND_WIDTH = 480
BACKGROUND_HEIGHT = 270

BACKGROUND_PACK_DEFS: list[dict[str, Any]] = [
    {
        "id": "imperial-scroll",
        "name": "帝卷金纹",
        "description": "卷轴、山势和鎏金边饰组成的历史叙事底图，适合纪传长卷式视频。",
        "recommended_templates": ["chronicle"],
        "semantic_tags": [
            "忠义",
            "守护",
            "帝王",
            "史传",
            "经典",
            "厚重",
            "贵气",
            "王者",
            "统御",
            "远志",
            "巡狩",
            "创业",
            "修行",
        ],
        "figure_keywords": [
            "关羽",
            "刘备",
            "李世民",
            "唐僧",
            "唐玄宗",
            "汉武帝",
            "周穆王",
            "帝",
            "王",
            "天子",
        ],
        "story_keywords": [
            "历史",
            "征战",
            "护送",
            "西行",
            "远征",
            "业绩",
            "创业",
            "王朝",
            "正典",
        ],
        "match_hint": "适合忠义、帝王、史传与守护气质的中国名马。",
        "palette": ["#1A120B", "#4A2E15", "#C8984B", "#F0D49A"],
        "style": "scroll",
        "assets": [
            {"id": "opening-scroll", "name": "卷首晨光", "description": "适合开篇点题和人物登场。"},
            {"id": "historical-map", "name": "山川古图", "description": "适合史料讲述和背景交代。"},
            {"id": "bronze-chronicle", "name": "金石纪传", "description": "适合中段推进和典籍感镜头。"},
            {"id": "epilogue-banner", "name": "落款题记", "description": "适合收束情绪和片尾文案。"},
        ],
    },
    {
        "id": "battlefield-ember",
        "name": "沙场赤焰",
        "description": "更偏冲阵和旌旗感的战报底图，适合战场、奔袭和高压叙事。",
        "recommended_templates": ["battle"],
        "semantic_tags": [
            "爆发",
            "冲锋",
            "威猛",
            "征战",
            "边疆",
            "逆境",
            "速度",
            "锋芒",
            "硬战",
            "夜战",
            "强攻",
            "野性",
            "压迫",
            "勇武",
            "执行",
        ],
        "figure_keywords": [
            "吕布",
            "项羽",
            "曹操",
            "秦琼",
            "尉迟恭",
            "罗成",
            "岳云",
            "猛将",
            "英雄",
        ],
        "story_keywords": [
            "冲阵",
            "厮杀",
            "边关",
            "兵败",
            "脱险",
            "夜战",
            "征伐",
            "奇袭",
            "硬战",
        ],
        "match_hint": "适合冲锋、爆发、边疆与征战气质的战阵型名马。",
        "palette": ["#140C0B", "#3A1610", "#B4472A", "#F59D52"],
        "style": "battle",
        "assets": [
            {"id": "campfire-dawn", "name": "营火破晓", "description": "适合战前蓄势和出征开场。"},
            {"id": "banner-charge", "name": "旌旗突进", "description": "适合主镜头冲锋和节奏拉满。"},
            {"id": "dust-clash", "name": "烟尘鏖战", "description": "适合中段爆发和压迫感转场。"},
            {"id": "victory-smoke", "name": "战后余烬", "description": "适合结尾余韵和人物定格。"},
        ],
    },
    {
        "id": "moonlit-legend",
        "name": "夜照传奇",
        "description": "月色、云海与神秘纹样构成的传说系底图，适合稀有马和高位角色。",
        "recommended_templates": ["legend"],
        "semantic_tags": [
            "神秘",
            "空灵",
            "传奇",
            "祥瑞",
            "稀有",
            "白马",
            "神异",
            "圣洁",
            "终局",
            "隐藏王者",
            "修行",
            "神话",
            "灵动",
            "贵重",
        ],
        "figure_keywords": [
            "赵云",
            "唐僧",
            "周穆王",
            "仙",
            "传说",
            "神马",
            "英魂",
        ],
        "story_keywords": [
            "月",
            "传奇",
            "神话",
            "西域",
            "八骏",
            "星",
            "光",
            "祥瑞",
            "稀世",
        ],
        "match_hint": "适合传奇、白马、空灵与神话向叙事的高稀有坐骑。",
        "palette": ["#08111D", "#17314A", "#5C7FA8", "#D2C18B"],
        "style": "legend",
        "assets": [
            {"id": "moon-gate", "name": "月门初现", "description": "适合传说马的高位登场。"},
            {"id": "cloud-passage", "name": "云海行迹", "description": "适合旅途、追风和命运感。"},
            {"id": "starlit-relic", "name": "星纹遗卷", "description": "适合细节讲述和藏品镜头。"},
            {"id": "silent-crown", "name": "静夜王座", "description": "适合片尾停驻和传说定格。"},
        ],
    },
]

BACKGROUND_GENERIC_STOPWORDS = {
    "",
    "名马",
    "人物",
    "故事",
    "传统",
    "中国",
    "古代",
    "历史",
}


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    normalized = value.strip().lstrip("#")
    return tuple(int(normalized[index : index + 2], 16) for index in range(0, 6, 2))


def _mix(color_a: tuple[int, int, int], color_b: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(color_a[index] + (color_b[index] - color_a[index]) * ratio) for index in range(3))


def _blend_pixel(buffer: bytearray, width: int, x: int, y: int, color: tuple[int, int, int], alpha: float) -> None:
    if x < 0 or y < 0 or x >= width:
        return
    alpha = max(0.0, min(1.0, alpha))
    pixel_index = (y * width + x) * 3
    original = (buffer[pixel_index], buffer[pixel_index + 1], buffer[pixel_index + 2])
    blended = _mix(original, color, alpha)
    buffer[pixel_index : pixel_index + 3] = bytes(blended)


def _set_pixel(buffer: bytearray, width: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if x < 0 or y < 0 or x >= width:
        return
    pixel_index = (y * width + x) * 3
    buffer[pixel_index : pixel_index + 3] = bytes(color)


def _draw_circle(
    buffer: bytearray,
    width: int,
    height: int,
    *,
    center_x: float,
    center_y: float,
    radius: float,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    min_x = max(0, int(center_x - radius - 1))
    max_x = min(width - 1, int(center_x + radius + 1))
    min_y = max(0, int(center_y - radius - 1))
    max_y = min(height - 1, int(center_y + radius + 1))
    radius_sq = radius * radius
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            distance_sq = (x - center_x) ** 2 + (y - center_y) ** 2
            if distance_sq > radius_sq:
                continue
            falloff = 1.0 - (distance_sq / radius_sq)
            _blend_pixel(buffer, width, x, y, color, alpha * falloff)


def _draw_rect(
    buffer: bytearray,
    width: int,
    height: int,
    *,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    for row in range(max(0, y), min(height, y + rect_height)):
        for col in range(max(0, x), min(width, x + rect_width)):
            _blend_pixel(buffer, width, col, row, color, alpha)


def _draw_ridge(
    buffer: bytearray,
    width: int,
    height: int,
    *,
    base_y: float,
    amplitude: float,
    frequency: float,
    shift: float,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    for x in range(width):
        normalized_x = x / max(1, width - 1)
        ridge = (
            base_y
            + amplitude * math.sin(normalized_x * math.pi * frequency + shift)
            + amplitude * 0.35 * math.sin(normalized_x * math.pi * frequency * 2.4 + shift * 0.7)
        )
        start_y = max(0, min(height - 1, int(ridge)))
        for y in range(start_y, height):
            depth = (y - start_y) / max(1, height - start_y)
            _blend_pixel(buffer, width, x, y, color, alpha * min(1.0, 0.45 + depth * 0.65))


def _draw_starfield(
    buffer: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    seed: int,
) -> None:
    count = 34
    for index in range(count):
        x = int(((index * 53 + seed * 17) % (width - 24)) + 12)
        y = int(((index * 29 + seed * 23) % int(height * 0.55)) + 10)
        radius = 1 + ((index + seed) % 3)
        _draw_circle(buffer, width, height, center_x=x, center_y=y, radius=radius, color=color, alpha=0.55)


def _apply_vignette(buffer: bytearray, width: int, height: int, *, strength: float) -> None:
    center_x = width / 2
    center_y = height / 2
    max_distance = math.sqrt(center_x**2 + center_y**2)
    for y in range(height):
        for x in range(width):
            distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            darkness = max(0.0, (distance / max_distance) ** 1.6 - 0.42) * strength
            _blend_pixel(buffer, width, x, y, (0, 0, 0), darkness)


def _generate_base_canvas(pack: dict[str, Any], asset_index: int) -> bytearray:
    top = _hex_to_rgb(pack["palette"][0])
    bottom = _hex_to_rgb(pack["palette"][1])
    accent = _hex_to_rgb(pack["palette"][2])
    glow = _hex_to_rgb(pack["palette"][3])

    width = BACKGROUND_WIDTH
    height = BACKGROUND_HEIGHT
    buffer = bytearray(width * height * 3)
    shift = asset_index * 0.21 + len(pack["id"]) * 0.04

    for y in range(height):
        v = y / max(1, height - 1)
        horizon = 0.12 * math.sin(v * math.pi * 3 + shift)
        row_color = _mix(top, bottom, min(1.0, max(0.0, v + horizon * 0.12)))
        for x in range(width):
            u = x / max(1, width - 1)
            stripe = (math.sin((u * 3.2 + v * 1.15 + shift) * math.pi) + 1) * 0.5
            glow_center_x = 0.22 + (asset_index % 4) * 0.18
            glow_strength = max(0.0, 1.0 - (((u - glow_center_x) * 1.9) ** 2 + ((v - 0.22) * 2.8) ** 2))
            color = _mix(row_color, accent, stripe * 0.08)
            color = _mix(color, glow, min(0.22, glow_strength * 0.26))
            _set_pixel(buffer, width, x, y, color)

    return buffer


def _decorate_scroll_pack(buffer: bytearray, pack: dict[str, Any], asset_index: int) -> None:
    width = BACKGROUND_WIDTH
    height = BACKGROUND_HEIGHT
    accent = _hex_to_rgb(pack["palette"][2])
    glow = _hex_to_rgb(pack["palette"][3])
    shadow = _hex_to_rgb(pack["palette"][1])

    _draw_circle(
        buffer,
        width,
        height,
        center_x=width * (0.18 + asset_index * 0.08),
        center_y=height * 0.18,
        radius=34 + asset_index * 8,
        color=glow,
        alpha=0.42,
    )
    _draw_ridge(buffer, width, height, base_y=height * 0.48, amplitude=18 + asset_index * 4, frequency=2.2, shift=0.3, color=shadow, alpha=0.34)
    _draw_ridge(buffer, width, height, base_y=height * 0.58, amplitude=24 + asset_index * 5, frequency=1.7, shift=1.2, color=accent, alpha=0.22)
    _draw_rect(buffer, width, height, x=18, y=22, rect_width=width - 36, rect_height=4, color=glow, alpha=0.42)
    _draw_rect(buffer, width, height, x=18, y=height - 26, rect_width=width - 36, rect_height=4, color=glow, alpha=0.42)
    _draw_rect(buffer, width, height, x=18, y=22, rect_width=4, rect_height=height - 44, color=glow, alpha=0.28)
    _draw_rect(buffer, width, height, x=width - 22, y=22, rect_width=4, rect_height=height - 44, color=glow, alpha=0.28)


def _decorate_battle_pack(buffer: bytearray, pack: dict[str, Any], asset_index: int) -> None:
    width = BACKGROUND_WIDTH
    height = BACKGROUND_HEIGHT
    accent = _hex_to_rgb(pack["palette"][2])
    glow = _hex_to_rgb(pack["palette"][3])
    shadow = _hex_to_rgb(pack["palette"][0])

    horizon_y = int(height * (0.58 + asset_index * 0.03))
    _draw_rect(buffer, width, height, x=0, y=horizon_y, rect_width=width, rect_height=height - horizon_y, color=shadow, alpha=0.38)
    for index in range(4):
        banner_x = 36 + index * 88 + asset_index * 12
        _draw_rect(buffer, width, height, x=banner_x, y=horizon_y - 72 - index * 8, rect_width=4, rect_height=95 + index * 18, color=glow, alpha=0.45)
        _draw_rect(buffer, width, height, x=banner_x + 4, y=horizon_y - 70 - index * 8, rect_width=34, rect_height=18 + index * 2, color=accent, alpha=0.35)
    _draw_ridge(buffer, width, height, base_y=height * 0.62, amplitude=16 + asset_index * 5, frequency=3.1, shift=0.8, color=accent, alpha=0.22)
    _draw_ridge(buffer, width, height, base_y=height * 0.74, amplitude=10 + asset_index * 3, frequency=4.4, shift=1.4, color=shadow, alpha=0.28)
    for index in range(18):
        spark_x = 28 + ((index * 41 + asset_index * 19) % (width - 56))
        spark_y = 18 + ((index * 17 + asset_index * 13) % int(height * 0.45))
        _draw_circle(buffer, width, height, center_x=spark_x, center_y=spark_y, radius=2 + (index % 2), color=glow, alpha=0.28)


def _decorate_legend_pack(buffer: bytearray, pack: dict[str, Any], asset_index: int) -> None:
    width = BACKGROUND_WIDTH
    height = BACKGROUND_HEIGHT
    accent = _hex_to_rgb(pack["palette"][2])
    glow = _hex_to_rgb(pack["palette"][3])
    shadow = _hex_to_rgb(pack["palette"][1])

    _draw_circle(
        buffer,
        width,
        height,
        center_x=width * (0.72 - asset_index * 0.08),
        center_y=height * 0.2,
        radius=30 + asset_index * 7,
        color=glow,
        alpha=0.46,
    )
    _draw_circle(
        buffer,
        width,
        height,
        center_x=width * (0.72 - asset_index * 0.08),
        center_y=height * 0.2,
        radius=48 + asset_index * 8,
        color=accent,
        alpha=0.12,
    )
    _draw_starfield(buffer, width, height, color=glow, seed=asset_index + 3)
    _draw_ridge(buffer, width, height, base_y=height * 0.6, amplitude=12 + asset_index * 3, frequency=1.9, shift=0.6, color=shadow, alpha=0.22)
    _draw_rect(buffer, width, height, x=40, y=height - 64, rect_width=width - 80, rect_height=22, color=accent, alpha=0.08)
    _draw_rect(buffer, width, height, x=54, y=height - 50, rect_width=width - 108, rect_height=6, color=glow, alpha=0.22)


def _generate_asset_pixels(pack: dict[str, Any], asset_index: int) -> bytearray:
    buffer = _generate_base_canvas(pack, asset_index)
    style = pack["style"]
    if style == "battle":
        _decorate_battle_pack(buffer, pack, asset_index)
    elif style == "legend":
        _decorate_legend_pack(buffer, pack, asset_index)
    else:
        _decorate_scroll_pack(buffer, pack, asset_index)
    _apply_vignette(buffer, BACKGROUND_WIDTH, BACKGROUND_HEIGHT, strength=0.58)
    return buffer


def _write_bmp(path: Path, width: int, height: int, pixels: bytearray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row_stride = width * 3
    padding = (4 - (row_stride % 4)) % 4
    image_size = (row_stride + padding) * height
    file_size = 54 + image_size

    header = bytearray()
    header.extend(b"BM")
    header.extend(file_size.to_bytes(4, "little"))
    header.extend((0).to_bytes(4, "little"))
    header.extend((54).to_bytes(4, "little"))
    header.extend((40).to_bytes(4, "little"))
    header.extend(width.to_bytes(4, "little", signed=True))
    header.extend(height.to_bytes(4, "little", signed=True))
    header.extend((1).to_bytes(2, "little"))
    header.extend((24).to_bytes(2, "little"))
    header.extend((0).to_bytes(4, "little"))
    header.extend(image_size.to_bytes(4, "little"))
    header.extend((2835).to_bytes(4, "little"))
    header.extend((2835).to_bytes(4, "little"))
    header.extend((0).to_bytes(4, "little"))
    header.extend((0).to_bytes(4, "little"))

    padding_bytes = b"\x00" * padding
    with path.open("wb") as file:
        file.write(header)
        for row in range(height - 1, -1, -1):
            start = row * row_stride
            end = start + row_stride
            row_data = bytearray()
            for index in range(start, end, 3):
                red, green, blue = pixels[index], pixels[index + 1], pixels[index + 2]
                row_data.extend((blue, green, red))
            file.write(row_data)
            if padding:
                file.write(padding_bytes)


def build_background_library(force: bool = False) -> dict[str, Any]:
    BACKGROUND_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    packs: list[dict[str, Any]] = []

    for pack_def in BACKGROUND_PACK_DEFS:
        pack_dir = BACKGROUND_LIBRARY_DIR / pack_def["id"]
        pack_dir.mkdir(parents=True, exist_ok=True)
        assets: list[dict[str, Any]] = []

        for asset_index, asset_def in enumerate(pack_def["assets"]):
            file_path = pack_dir / f"{asset_def['id']}.bmp"
            if force or not file_path.exists():
                pixels = _generate_asset_pixels(pack_def, asset_index)
                _write_bmp(file_path, BACKGROUND_WIDTH, BACKGROUND_HEIGHT, pixels)

            relative_path = file_path.relative_to(ASSET_ROOT).as_posix()
            file_url = f"/assets/{relative_path}"
            assets.append(
                {
                    "id": asset_def["id"],
                    "name": asset_def["name"],
                    "description": asset_def["description"],
                    "scene_index": asset_index + 1,
                    "file_url": file_url,
                    "file_path": str(file_path),
                }
            )

        packs.append(
            {
                "id": pack_def["id"],
                "name": pack_def["name"],
                "description": pack_def["description"],
                "recommended_templates": list(pack_def["recommended_templates"]),
                "semantic_tags": list(pack_def.get("semantic_tags", [])),
                "figure_keywords": list(pack_def.get("figure_keywords", [])),
                "story_keywords": list(pack_def.get("story_keywords", [])),
                "match_hint": str(pack_def.get("match_hint", "")).strip(),
                "asset_count": len(assets),
                "preview_url": assets[0]["file_url"],
                "assets": assets,
            }
        )

    manifest = {
        "version": 3,
        "width": BACKGROUND_WIDTH,
        "height": BACKGROUND_HEIGHT,
        "packs": packs,
    }
    BACKGROUND_MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_background_library(force: bool = False) -> dict[str, Any]:
    if force or not BACKGROUND_MANIFEST_PATH.exists():
        return build_background_library(force=True)

    try:
        manifest = json.loads(BACKGROUND_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return build_background_library(force=True)

    if int(manifest.get("version", 0) or 0) < 3:
        return build_background_library(force=True)

    for pack in manifest.get("packs", []):
        if "semantic_tags" not in pack or "match_hint" not in pack or "figure_keywords" not in pack or "story_keywords" not in pack:
            return build_background_library(force=True)
        for asset in pack.get("assets", []):
            file_path = Path(str(asset.get("file_path", "")))
            if not file_path.exists():
                return build_background_library(force=True)
    return manifest


def list_background_packs() -> list[dict[str, Any]]:
    manifest = load_background_library()
    return list(manifest.get("packs", []))


def _normalize_matching_terms(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        term = str(value or "").strip().lower()
        if not term or term in BACKGROUND_GENERIC_STOPWORDS or term in normalized:
            continue
        normalized.append(term)
    return normalized


def _build_horse_terms(horse_profile: dict[str, Any] | None) -> tuple[list[str], str]:
    if not horse_profile:
        return [], ""

    labels = [str(label).strip() for label in horse_profile.get("labels", []) if str(label).strip()]
    text_parts = [
        str(horse_profile.get("name", "")).strip(),
        str(horse_profile.get("figure", "")).strip(),
        str(horse_profile.get("source", "")).strip(),
        str(horse_profile.get("story", "")).strip(),
        *labels,
    ]
    haystack = " ".join(part for part in text_parts if part).lower()
    return _normalize_matching_terms(labels), haystack


def recommend_background_pack(
    pack_id: str | None,
    scene_template: str | None = None,
    horse_profile: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    packs = list_background_packs()
    normalized_pack_id = str(pack_id or "").strip().lower()
    if normalized_pack_id:
        for pack in packs:
            if pack["id"] == normalized_pack_id:
                return pack, {
                    "mode": "manual",
                    "reason": f"使用手动指定的背景素材包：{pack['name']}",
                    "matched_tags": [],
                    "score": 999.0,
                }

    normalized_template = str(scene_template or "").strip().lower()
    if not packs:
        raise RuntimeError("Background library is empty")

    labels, haystack = _build_horse_terms(horse_profile)
    if horse_profile and (labels or haystack):
        ranked: list[tuple[float, dict[str, Any], list[str], bool]] = []
        for pack in packs:
            score = 0.0
            matched: list[str] = []

            pack_terms = _normalize_matching_terms([str(tag) for tag in pack.get("semantic_tags", [])])
            for term in pack_terms:
                if any(term in label or label in term for label in labels):
                    matched.append(term)
                    score += 4.0
                elif term in haystack:
                    matched.append(term)
                    score += 1.6

            for keyword in _normalize_matching_terms([str(item) for item in pack.get("figure_keywords", [])]):
                if keyword in haystack:
                    matched.append(keyword)
                    score += 2.2

            for keyword in _normalize_matching_terms([str(item) for item in pack.get("story_keywords", [])]):
                if keyword in haystack:
                    matched.append(keyword)
                    score += 1.4

            template_hit = bool(normalized_template and normalized_template in pack.get("recommended_templates", []))
            if template_hit:
                score += 2.0

            ranked.append((score, pack, list(dict.fromkeys(matched))[:4], template_hit))

        ranked.sort(key=lambda item: (item[0], 1 if item[3] else 0, len(item[2])), reverse=True)
        best_score, best_pack, matched_terms, template_hit = ranked[0]
        if best_score > 0:
            matched_display = "、".join(matched_terms[:3]) if matched_terms else best_pack["name"]
            suffix = "，并且与当前分镜模板相符" if template_hit else ""
            return best_pack, {
                "mode": "smart",
                "reason": f"根据马匹标签与故事关键词匹配到 {matched_display}{suffix}",
                "matched_tags": matched_terms,
                "score": round(best_score, 2),
            }

    for pack in packs:
        if normalized_template and normalized_template in pack.get("recommended_templates", []):
            return pack, {
                "mode": "template",
                "reason": f"未命中马匹语义标签，按分镜模板推荐 {pack['name']}",
                "matched_tags": [],
                "score": 1.0,
            }

    return packs[0], {
        "mode": "default",
        "reason": f"使用默认背景素材包 {packs[0]['name']}",
        "matched_tags": [],
        "score": 0.0,
    }


def resolve_background_pack(
    pack_id: str | None,
    scene_template: str | None = None,
    horse_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pack, _ = recommend_background_pack(pack_id, scene_template, horse_profile=horse_profile)
    return pack


def resolve_background_assets(pack_id: str | None, scene_template: str | None, scene_count: int) -> list[dict[str, Any]]:
    pack = resolve_background_pack(pack_id, scene_template)
    assets = list(pack.get("assets", []))
    if not assets:
        raise RuntimeError(f"Background pack '{pack['id']}' has no assets")
    return [assets[index % len(assets)] for index in range(max(1, scene_count))]
