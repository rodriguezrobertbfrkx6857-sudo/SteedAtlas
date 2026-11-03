import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "wangzhan/{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server"
sys.path.insert(0, str(SERVER))
os.environ.update(
    DATABASE_URL="sqlite:///" + (ROOT / "runtime/test-bootstrap.db").as_posix(),
    DEBUG="false",
    SECRET_KEY="test-only-" + ("a" * 48),
    STEEDATLAS_ROOT=str(ROOT),
    VIDEO_FACTORY_API_MODE="off",
    WORKFLOW_RUNTIME_REDIS_ENABLED="false",
)

import pytest
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.services.auth import create_access_token
from app.v2 import runtime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class PrivateTestContext(tuple):
    def __repr__(self):
        return "<isolated test client, session factory, redacted test authentication>"


@pytest.fixture()
def system(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///" + (tmp_path / "isolated.db").as_posix(), connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        for identity, role in [("alice", "user"), ("bob", "user"), ("staff", "operator"), ("admin", "admin")]:
            db.add(User(id=identity, nickname=identity, role=role))
        db.commit()

    def db_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(runtime, "SessionLocal", factory)
    headers = {i: {"Authorization": "Bearer " + create_access_token(i)} for i in ["alice", "bob", "staff", "admin"]}
    with TestClient(app) as client:
        yield PrivateTestContext((client, factory, headers))
    app.dependency_overrides.clear()
    engine.dispose()


def project_data():
    return {
        "title": "三幕中文演示",
        "scenes": [
            {"id": f"s{i}", "text": f"场景{i}：循着记载，认识名马。", "duration_ticks": 24} for i in range(1, 4)
        ],
    }


def new_project(client, headers):
    response = client.post("/api/v2/projects", json=project_data(), headers=headers["alice"])
    assert response.status_code == 201, response.text
    return response.json()


def approved_job(client, headers):
    p = new_project(client, headers)
    approved = client.post(
        "/api/v2/projects/" + p["id"] + "/approve",
        headers=headers["alice"],
        json={"expected_version": 1, "idempotency_key": "approval-one"},
    ).json()
    job = client.post(
        "/api/v2/projects/" + p["id"] + "/renders",
        headers=headers["alice"],
        json={"expected_version": approved["version"], "idempotency_key": "render-one"},
    )
    assert job.status_code == 202, job.text
    return p, job.json()
