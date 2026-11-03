from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.database import SessionLocal
from app.models.user import User
from app.models.workflow_task import WorkflowTask
from app.services.workflow_tasks import (
    build_initial_node_states,
    default_workflow_definition,
    generate_workflow_task_id,
    run_site_workflow_task,
)


PROJECT_DIR = SERVER_DIR.parents[5]
TEST_VIDEO_MODEL = os.environ.get("VIDEO_FACTORY_MINIMAL_TEST_MODEL", "veo_3_1-fast-components-4K").strip() or "veo_3_1-fast-components-4K"


def _minimal_workflow_definition() -> dict:
    keep = {"input", "script", "storyboard", "keyframe", "voice", "subtitle", "veo", "compose", "output"}
    definition = default_workflow_definition()
    return {
        "name": "pixelle-minimal-quality-test",
        "mode": "site-workflow",
        "nodes": [node for node in definition.get("nodes", []) if node.get("id") in keep],
        "connections": [],
    }


def _generated_path(video_url: str) -> Path | None:
    if not video_url.startswith("/generated/"):
        return None
    relative = video_url.removeprefix("/generated/").lstrip("/\\")
    path = (SERVER_DIR / "generated" / relative).resolve()
    root = (SERVER_DIR / "generated").resolve()
    if not str(path).startswith(str(root)) or not path.exists():
        return None
    return path


def main() -> None:
    session = SessionLocal()
    try:
        user = session.query(User).first()
        if user is None:
            user = User(
                id=f"local_test_{uuid.uuid4().hex[:10]}",
                nickname="local-video-test",
                role="admin",
            )
            session.add(user)
            session.commit()

        workflow_definition = _minimal_workflow_definition()
        task_id = generate_workflow_task_id()
        input_payload = {
            "topic": "赤兔马为什么被称为三国第一名马，用一个紧张但清楚的瞬间讲出来",
            "horse": "赤兔",
            "horse_name": "赤兔",
            "duration": 8,
            "aspect_ratio": "9:16",
            "reference": {"enabled": False},
            "enableXhsPublish": False,
            "script": {
                "style": "真实历史讲解",
                "temperature": 0.45,
                "customPrompt": "只做一个镜头，旁白必须是自然中文口语，不要像广告词。",
            },
            "storyboard": {
                "shotCount": 1,
                "shotSeconds": 8,
                "visualStyle": "国风水墨画卷展开，但画面构图和动作必须重新设计，不照搬样片",
                "camera": "低角度缓慢推进，然后跟随马蹄扬起尘土",
                "promptGuidance": "一个完整动作：赤兔从烟尘中冲出，骑手勒缰回望，观众能看清马的力量和主人之间的关系。",
            },
            "keyframe": {
                "referenceMode": "每个分镜 1 张关键帧",
                "frameCount": 1,
                "promptStyle": "电影级关键帧，清晰主体，真实马匹结构，水墨质感只是风格，不要静态海报",
                "consistency": "同一匹赤色战马、同一骑手、同一光线与战场方向",
            },
            "veo": {
                "model": TEST_VIDEO_MODEL,
                "__modelLocked": "1",
                "parallel": 1,
                "generateAudio": "是",
                "quality": "fast-preview",
                "motionPrompt": "必须有明显运动，马匹奔跑、烟尘后移、镜头缓慢推进，最后不要静止超过一秒。",
                "negativePrompt": "static poster, frozen image, slideshow, no audio, English voice, text overlay, watermark, malformed horse legs",
            },
            "voice": {
                "mode": "Veo 原生音频优先",
                "voice": "自然中文男声",
                "emotion": "沉稳、有压迫感、像历史故事讲解",
                "soundscape": "低沉鼓点、马蹄声、远处风声，旁白清晰优先",
            },
            "subtitle": {
                "mode": "仅站内 SRT",
                "style": "金色下三分之一",
                "language": "简体中文",
            },
            "compose": {
                "engine": "FFmpeg / 网站后端",
                "transition": "单镜头直出",
                "ducking": "中文旁白优先",
            },
            "output": {"saveTo": "网站 generated/videos"},
        }
        task = WorkflowTask(
            id=task_id,
            user_id=user.id,
            title=input_payload["topic"],
            horse_name="赤兔",
            status="draft",
            progress=0,
            current_node="input",
            aspect_ratio="9:16",
            duration=8,
            callback_token=uuid.uuid4().hex,
            workflow_definition=workflow_definition,
            input_payload=input_payload,
            normalized_payload={},
            node_states=build_initial_node_states(workflow_definition),
            result_payload={},
            dispatch_response={},
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(task)
        session.commit()
    finally:
        session.close()

    run_result = run_site_workflow_task(task_id, step_delay_seconds=0.05)

    session = SessionLocal()
    try:
        task = session.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
        result_payload = task.result_payload if task and isinstance(task.result_payload, dict) else {}
        video_url = str(result_payload.get("videoUrl") or "")
        local_path = _generated_path(video_url)
        copied_path = ""
        if local_path:
            target = PROJECT_DIR / "视频工厂_Pixelle最小测试.mp4"
            shutil.copyfile(local_path, target)
            copied_path = str(target)
        summary = {
            "taskId": task_id,
            "status": task.status if task else run_result.get("dispatch_status"),
            "message": run_result.get("message"),
            "videoUrl": video_url,
            "localVideoPath": str(local_path) if local_path else "",
            "copiedVideoPath": copied_path,
            "reviewReport": result_payload.get("reviewReport", {}),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
