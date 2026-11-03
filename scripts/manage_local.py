"""Explicit local-only operator command; never points to a production database."""

import argparse
import os
import sys

from paths import ROOT, SERVER

parser = argparse.ArgumentParser()
parser.add_argument("--user-id", required=True)
parser.add_argument("--role", choices=["admin", "operator", "user"], required=True)
args = parser.parse_args()
database = ROOT / "runtime/steedatlas.db"
if not database.exists():
    raise SystemExit("Initialize local V2 database first")
os.environ.update(DATABASE_URL="sqlite:///" + database.as_posix(), DEBUG="false")
sys.path.insert(0, str(SERVER))
from app.database import SessionLocal
from app.models.user import User
from app.v2.domain import emit

with SessionLocal() as db:
    user = db.get(User, args.user_id)
    if not user:
        raise SystemExit("User not found; use the ID returned by /api/v1/auth/me")
    user.role = args.role
    emit(db, user.id, "local-operator", "LOCAL_ROLE_CHANGE", {"role": args.role})
    db.commit()
print("Local role updated with audit event. No production database was accessed.")
