"""Seed legendary horse profiles into DB and optionally generate luxe images via gpt-image-2."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.horse import Horse
from app.services.video_factory_providers import (
    VideoFactoryProviderError,
    VideoFactoryProviderNotConfigured,
    generate_keyframe_image,
)

SERVER_DIR = Path(__file__).resolve().parents[1]
DATA_BASE_FILE = "legendary_horses_top5.json"
DATA_BATCH_GLOB = "legendary_horses_batch*.json"
GENERATED_DIR = SERVER_DIR / "generated"
HORSE_LIBRARY_DIR = GENERATED_DIR / "horse-library"


def _profile_paths() -> tuple[Path, ...]:
    data_root = SERVER_DIR / "data"
    candidates: list[Path] = [data_root / DATA_BASE_FILE]
    candidates.extend(sorted(data_root.glob(DATA_BATCH_GLOB)))
    resolved: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve())
        if key in seen:
            continue
        seen.add(key)
        resolved.append(candidate)
    return tuple(resolved)


def _load_profiles() -> list[dict]:
    merged: list[dict] = []
    seen_ids: set[str] = set()
    for profile_path in _profile_paths():
        if not profile_path.exists():
            continue
        with profile_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"{profile_path} is not a list")
        default_priority = "top5" if profile_path.name == DATA_BASE_FILE else profile_path.stem
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            horse_id = str(item.get("id") or "").strip()
            dedupe_key = horse_id or f"{profile_path.name}#{index}"
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            normalized = dict(item)
            normalized.setdefault("priority", default_priority)
            merged.append(normalized)
    return merged


def _url_to_local_path(url: str) -> Path | None:
    text = str(url or "").strip()
    if not text.startswith("/generated/"):
        return None
    rel = text.removeprefix("/generated/").lstrip("/\\")
    path = (GENERATED_DIR / rel).resolve()
    if GENERATED_DIR.resolve() not in path.parents and path != GENERATED_DIR.resolve():
        return None
    return path if path.exists() and path.is_file() else None


def _ensure_luxe_image(profile: dict, *, generate_images: bool, scene: int) -> str:
    HORSE_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    image_file = str(profile.get("image_file") or f"{profile.get('id')}.png").strip()
    image_file = "".join(ch for ch in image_file if ch.isalnum() or ch in {"-", "_", "."}) or f"{profile.get('id')}.png"
    target = HORSE_LIBRARY_DIR / image_file
    final_url = f"/generated/horse-library/{image_file}"
    fallback_url = str(profile.get("image_url") or "").strip()

    if target.exists() and target.stat().st_size > 0:
        return final_url
    if not generate_images:
        return fallback_url or final_url

    prompt = str(profile.get("image_prompt") or "").strip()
    if not prompt:
        raise ValueError(f"{profile.get('name')} has empty image_prompt")

    result = generate_keyframe_image(
        task_id="legendary-horse-db",
        scene=scene,
        prompt=prompt,
    )
    source_url = str(result.get("imageUrl") or "").strip()
    source = _url_to_local_path(source_url)
    if source is None:
        raise RuntimeError(f"Image provider returned non-local URL: {source_url or '<empty>'}")
    shutil.copy2(source, target)
    return final_url


def _compose_full_story(profile: dict) -> str:
    horse_story = str(profile.get("horse_life_story") or "").strip()
    owner_story = str(profile.get("owner_life_story") or "").strip()
    base_story = str(profile.get("full_story") or "").strip()
    parts: list[str] = []
    if horse_story:
        parts.append(f"名马生平：{horse_story}")
    if owner_story:
        parts.append(f"主人生平：{owner_story}")
    if base_story:
        parts.append(f"视频创作建议：{base_story}")
    return "\n\n".join(parts).strip()


def seed(*, generate_images: bool) -> None:
    profiles = _load_profiles()
    session = SessionLocal()
    try:
        for idx, profile in enumerate(profiles, start=1):
            horse_id = str(profile.get("id") or "").strip()
            if not horse_id:
                continue
            horse = session.query(Horse).filter(Horse.id == horse_id).first()
            if horse is None:
                horse = Horse(
                    id=horse_id,
                    name=str(profile.get("name") or horse_id).strip(),
                    title=str(profile.get("trait") or "历史名马").strip() or "历史名马",
                    rarity="SSR",
                    image="/images/chitu.png",
                    story=str(profile.get("story") or "").strip() or "历史名马",
                    full_story="",
                    historical_source=str(profile.get("historical_source") or "").strip(),
                    dynasty=str(profile.get("dynasty") or "").strip(),
                    owner=str(profile.get("owner") or "").strip(),
                    trait=str(profile.get("trait") or "历史名马").strip() or "历史名马",
                    traits=list(profile.get("traits") or profile.get("labels") or []),
                    drop_rate=1.0,
                    price=399.0,
                )
                session.add(horse)

            horse.name = str(profile.get("name") or horse.name).strip() or horse.name
            horse.title = str(profile.get("trait") or horse.title).strip() or horse.title
            horse.story = str(profile.get("story") or horse.story).strip() or horse.story
            horse.full_story = _compose_full_story(profile) or horse.full_story
            horse.historical_source = str(profile.get("historical_source") or horse.historical_source).strip()
            horse.dynasty = str(profile.get("dynasty") or horse.dynasty).strip()
            horse.owner = str(profile.get("owner") or horse.owner).strip()
            horse.trait = str(profile.get("trait") or horse.trait).strip() or horse.trait
            horse.traits = list(profile.get("traits") or profile.get("labels") or horse.traits or [])

            try:
                horse.image = _ensure_luxe_image(profile, generate_images=generate_images, scene=idx)
                print(f"[OK] {horse.name}: image -> {horse.image}")
            except (VideoFactoryProviderNotConfigured, VideoFactoryProviderError, RuntimeError, ValueError) as exc:
                print(f"[WARN] {horse.name}: image not updated ({exc})")

        session.commit()
        print(f"[DONE] Legendary horses are updated in database. total={len(profiles)}")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-image", action="store_true", help="skip gpt-image-2 generation")
    args = parser.parse_args()
    seed(generate_images=not args.no_image)


if __name__ == "__main__":
    main()
