import os
import subprocess
import sys
import time

from app.v2.models import Node
from conftest import SERVER, approved_job
from sqlalchemy import select


def test_actual_worker_process_crash_and_restart(system):
    c, f, h = system
    p, j = approved_job(c, h)
    with f() as db:
        url = str(db.get_bind().url)
    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(SERVER)}
    # A process obtains a durable lease, then exits abruptly before producing output.
    code = "import os;from app.database import SessionLocal;from app.v2.runtime import lease;db=SessionLocal();assert lease(db,'crashing');os._exit(17)"
    crashed = subprocess.run([sys.executable, "-c", code], env=env, cwd=SERVER, capture_output=True)
    assert crashed.returncode == 17
    with f() as db:
        n = db.scalar(select(Node).where(Node.job_id == j["id"], Node.state == "RUNNING"))
        assert n is not None
        n.lease_until = time.time() - 1
        db.commit()
    # Fresh process and fresh SQLAlchemy sessions reconstruct the job from the database.
    code = "from app.v2.runtime import work_once\nfor i in range(12):\n if not work_once('restarted'): break"
    restarted = subprocess.run([sys.executable, "-c", code], env=env, cwd=SERVER, capture_output=True, timeout=120)
    assert restarted.returncode == 0, restarted.stderr.decode(errors="replace")
    state = c.get("/api/v2/jobs/" + j["id"], headers=h["alice"]).json()
    assert state["status"] == "SUCCEEDED", state
    assert any(n["attempts"] == 2 for n in state["nodes"])
