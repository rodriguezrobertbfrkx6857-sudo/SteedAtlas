"""Create a real API-driven CPU sample, with original plates and a synthetic tone (not narration)."""

import json
import os
import sys
import time
import uuid

import httpx
from paths import ROOT, SERVER

sys.path.insert(0, str(SERVER))
os.environ["STEEDATLAS_ROOT"] = str(ROOT)
from app.v2 import media

out = ROOT / "deliverables"
out.mkdir(exist_ok=True)
inputs = ROOT / "runtime/demo-inputs"
inputs.mkdir(parents=True, exist_ok=True)
client = httpx.Client(base_url="http://127.0.0.1:8002", timeout=60)


def call(method, path, **kw):
    r = client.request(method, path, **kw)
    r.raise_for_status()
    return r.json()


identity = "demo-" + uuid.uuid4().hex[:10]
account = call(
    "POST",
    "/api/v1/auth/register",
    json={"phone": identity, "nickname": "本地真实视频验收", "password": uuid.uuid4().hex},
)
client.headers["Authorization"] = "Bearer " + account["access_token"]
scenes = [
    {"id": "s1", "text": "赤兔：从名马档案开始，分辨历史与想象。", "duration_ticks": 72},
    {"id": "s2", "text": "每段叙述，都应保留它的出处与边界。", "duration_ticks": 72},
    {"id": "s3", "text": "百骑谱，让故事有据可循。此片为艺术演绎。", "duration_ticks": 72},
]
p = call("POST", "/api/v2/projects", json={"title": "百骑谱 CPU 有声三幕验收", "scenes": scenes})
project = p["data"]
assets = []
for i, s in enumerate(project["scenes"]):
    plate = inputs / f"plate-{i}.png"
    media.template(plate, i)
    with plate.open("rb") as f:
        a = call(
            "POST",
            f"/api/v2/projects/{p['id']}/assets",
            files={"file": (plate.name, f, "image/png")},
            data={"rights": "OWNED"},
        )
    s["asset_id"] = a["id"]
    assets.append({"id": a["id"], "sha256": a["data"]["sha256"], "license": "Original programmatic illustration"})
audio = inputs / "tone.wav"
media.run(
    [
        media.FFMPEG,
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=220:sample_rate=48000:duration=9",
        "-af",
        "volume=0.04",
        str(audio),
    ]
)
with audio.open("rb") as f:
    a = call(
        "POST",
        f"/api/v2/projects/{p['id']}/assets",
        files={"file": ("tone.wav", f, "audio/wav")},
        data={"rights": "OWNED"},
    )
project["audio_asset_ids"] = [a["id"]]
assets.append({"id": a["id"], "sha256": a["data"]["sha256"], "license": "Synthetic test tone; not narration"})
p = call("PATCH", f"/api/v2/projects/{p['id']}/revisions", json={"expected_version": p["version"], "project": project})
p = call(
    "POST",
    f"/api/v2/projects/{p['id']}/approve",
    json={"expected_version": p["version"], "idempotency_key": uuid.uuid4().hex},
)
job = call(
    "POST",
    f"/api/v2/projects/{p['id']}/renders",
    json={"expected_version": p["version"], "idempotency_key": uuid.uuid4().hex},
)
deadline = time.time() + 180
while time.time() < deadline:
    state = call("GET", "/api/v2/jobs/" + job["id"])
    if state["status"] not in {"READY", "RUNNING"}:
        break
    time.sleep(0.5)
assert state["status"] == "SUCCEEDED", state
for kind, name in [("qa", "steedatlas-cpu-demo.mp4"), ("subtitle", "steedatlas-cpu-demo.srt")]:
    node = next(n for n in state["nodes"] if n["kind"] == kind)
    response = client.get(node["download"])
    response.raise_for_status()
    (out / name).write_bytes(response.content)
trace = call(
    "POST",
    f"/api/v2/projects/{p['id']}/agent-runs",
    json={"expected_version": p["version"], "mode": "RULE_BASED", "intent": "plan"},
)
manifest = {
    "mode": "REAL_CPU_FFMPEG_NO_MODEL",
    "audio": "Synthetic test tone, not speech or TTS",
    "project": call("GET", f"/api/v2/projects/{p['id']}/export"),
    "assets": assets,
    "job": state,
    "events": call("GET", f"/api/v2/jobs/{job['id']}/events"),
    "trace": trace,
    "probe": media.verify(out / "steedatlas-cpu-demo.mp4", 9),
}
(out / "demo-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
media.run(
    [
        media.FFMPEG,
        "-y",
        "-v",
        "error",
        "-ss",
        "4",
        "-i",
        str(out / "steedatlas-cpu-demo.mp4"),
        "-frames:v",
        "1",
        str(out / "demo-frame.png"),
    ]
)
print(json.dumps(manifest["probe"], ensure_ascii=True))
