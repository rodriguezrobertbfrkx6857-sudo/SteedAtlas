"""Bounded queue persistence comparison. This is not a production framework benchmark."""

import json
from pathlib import Path

from huey import SqliteHuey

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "runtime/huey-poc.db"
queue = SqliteHuey("steedatlas-poc", filename=str(path), immediate=False)


@queue.task()
def add(a, b):
    return a + b


add(1, 2)
before = len(queue)
reopened = SqliteHuey("steedatlas-poc", filename=str(path), immediate=False)
survives = len(reopened) == before
task = queue.dequeue()
after_dequeue = len(queue)
queue.execute(task)
result = {
    "candidate": "Huey 3.5.3 SqliteHuey",
    "license": "MIT",
    "pending_survives_reopen": survives,
    "queue_before": before,
    "queue_after_dequeue": after_dequeue,
    "dequeue_then_execute": "PASS",
    "not_tested": ["provider submission semantics", "same fault matrix as V2", "production concurrency"],
    "decision": "Keep V2 DB worker provisionally: project-specific fencing/ACL/evidence state already tested; not evidence that Huey is generally less reliable.",
}
(ROOT / "reports/runtime-poc.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result))
