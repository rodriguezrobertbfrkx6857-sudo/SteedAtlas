"""Cross-process, persistent local acquisition quota; no external services."""

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException


@contextmanager
def acquisition_slot(path, owner):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    with sqlite3.connect(path, timeout=5) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS acquisition_reservation (token TEXT PRIMARY KEY, owner TEXT, started REAL, expires REAL)"
        )
        db.execute("BEGIN IMMEDIATE")
        now = time.time()
        if db.execute("SELECT count(*) FROM acquisition_reservation WHERE expires > ?", (now,)).fetchone()[0]:
            raise HTTPException(429, "ACQUISITION_INSTANCE_BUSY")
        count, personal = db.execute(
            "SELECT count(*), coalesce(sum(owner = ?),0) FROM acquisition_reservation WHERE started > ?",
            (owner, now - 3600),
        ).fetchone()
        if count >= 12 or personal >= 3:
            raise HTTPException(429, "ACQUISITION_HOURLY_QUOTA")
        # Long conservative lease also covers slow parsing/commit after network timeout.
        db.execute("INSERT INTO acquisition_reservation VALUES (?,?,?,?)", (token, owner, now, now + 300))
    try:
        yield
    finally:
        with sqlite3.connect(path, timeout=5) as db:
            db.execute("UPDATE acquisition_reservation SET expires=0 WHERE token=?", (token,))
