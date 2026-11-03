import pytest
from app.config import Settings
from app.v2.security import public_url
from conftest import new_project
from pydantic import ValidationError


def test_knowledge_write_auth_and_path(system):
    c, db, h = system
    assert c.post("/api/v1/ai/build", json={"docs": []}).status_code == 401
    assert c.post("/api/v1/ai/build", headers=h["alice"], json={"docs": []}).status_code == 403
    assert (
        c.post("/api/v1/ai/build", headers=h["admin"], json={"docs": [], "out_path": "../../outside"}).status_code
        == 422
    )
    assert c.put("/api/v1/horses/rag-library/chitu", headers=h["alice"], json={"story": "alter"}).status_code == 403


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/x",
        "https://127.0.0.1/x",
        "https://169.254.169.254/",
        "file:///etc/passwd",
        "https://a.example:8443/x",
        "https://u:p@host/x",
    ],
)
def test_ssrf_fail_closed(url):
    with pytest.raises(Exception):
        public_url(url)


def test_production_config():
    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", DEBUG=True)
    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", DEBUG=False, SECRET_KEY="weak")
    assert Settings(APP_ENV="production", DEBUG=False, SECRET_KEY="z" * 48).APP_ENV == "production"


def test_object_scope_and_forged_paths(system):
    c, db, h = system
    p = new_project(c, h)
    assert c.get("/api/v2/projects/" + p["id"], headers=h["bob"]).status_code == 404
    assert c.get("/api/v2/projects/" + p["id"]).status_code == 401
    assert c.get("/generated/private.mp4").status_code == 401
    assert c.post("/api/v1/video/workflow/tasks", headers=h["alice"], json={}).status_code == 409


def test_upload_decode_rejects_fake_image(system):
    c, db, h = system
    p = new_project(c, h)
    r = c.post(
        "/api/v2/projects/" + p["id"] + "/assets",
        headers=h["alice"],
        files={"file": ("horse.png", b"not a real image", "image/png")},
    )
    assert r.status_code == 422


def test_upload_rejects_playlist_indirection(system):
    c, db, h = system
    p = new_project(c, h)
    playlist = b"ffconcat version 1.0\nfile http://127.0.0.1/secret.mp4\n"
    r = c.post(
        "/api/v2/projects/" + p["id"] + "/assets",
        headers=h["alice"],
        files={"file": ("video.mp4", playlist, "video/mp4")},
    )
    assert r.status_code == 422
