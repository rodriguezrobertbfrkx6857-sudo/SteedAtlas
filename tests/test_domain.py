import copy

import pytest
from app.v2.contracts import Project
from app.v2.domain import accept_patches, canonical_timeline, create, digest, impact, rank, select_roles
from app.v2.runtime import validate_dag
from conftest import new_project, project_data


def test_dag_rejects_cycle_missing_kind():
    with pytest.raises(ValueError):
        validate_dag([{"key": "a", "kind": "segment", "deps": ["a"]}])
    with pytest.raises(ValueError):
        validate_dag([{"key": "a", "kind": "shell", "deps": []}])
    with pytest.raises(ValueError):
        validate_dag([{"key": "a", "kind": "segment", "deps": ["missing"]}])
    with pytest.raises(ValueError):
        validate_dag([{"key": "a", "kind": "segment", "deps": []}, {"key": "a", "kind": "segment", "deps": []}])


def test_rational_timeline_and_validation():
    p = Project.model_validate(project_data()).model_dump()
    t = canonical_timeline(p)
    assert t["duration_ticks"] == 72 and t["tracks"][0]["clips"][1]["start_tick"] == 24
    p["scenes"][0]["duration_ticks"] = -1
    with pytest.raises(Exception):
        Project.model_validate(p)


def test_local_change_and_conservative_evidence():
    old = Project.model_validate(project_data()).model_dump()
    new = copy.deepcopy(old)
    new["scenes"][1]["text"] = "仅修改字幕"
    result = impact(old, new)
    assert result["s1"]["decision"] == "REUSE_ALLOWED"
    assert result["s2"]["decision"] == "REBUILD_REQUIRED"
    assert result["s2"]["asset"] == "REUSE_ALLOWED"
    assert all(x["decision"] == "REVIEW_REQUIRED" for x in impact(old, new, "claim").values())


def test_roles_and_no_self_authorization():
    p = Project.model_validate(project_data()).model_dump()
    assert select_roles(p, "subtitle")[0] == []
    assert select_roles(p, "plan")[0] == ["DIRECTOR", "REVIEW"]
    with pytest.raises(Exception):
        accept_patches(p, [{"path": "/review_state", "value": "APPROVED"}])


def test_cas_and_stale_proposal(system):
    c, db, h = system
    p = new_project(c, h)
    proposal = c.post(
        "/api/v2/projects/" + p["id"] + "/agent-runs", headers=h["alice"], json={"expected_version": 1}
    ).json()
    data = p["data"]
    data["title"] = "用户先修改"
    assert (
        c.patch(
            "/api/v2/projects/" + p["id"] + "/revisions",
            headers=h["alice"],
            json={"expected_version": 1, "project": data},
        ).status_code
        == 200
    )
    assert (
        c.patch(
            "/api/v2/projects/" + p["id"] + "/revisions",
            headers=h["alice"],
            json={"expected_version": 1, "project": data},
        ).status_code
        == 409
    )
    assert (
        c.post(
            "/api/v2/agent-proposals/" + proposal["id"] + "/review",
            headers=h["alice"],
            json={"expected_version": 2, "decision": "ACCEPT"},
        ).status_code
        == 409
    )
    assert (
        c.post(
            "/api/v2/projects/" + p["id"] + "/agent-runs",
            headers=h["alice"],
            json={"expected_version": 2, "mode": "LIVE_LLM"},
        ).status_code
        == 409
    )
    assert len(c.get("/api/v2/projects/" + p["id"] + "/revisions", headers=h["alice"]).json()) == 2


def test_bm25_alias_and_prompt_as_data():
    docs = [{"id": "a", "text": "赤兔 吕布 良马"}, {"id": "b", "text": "乌骓 项羽"}]
    assert rank("赤菟", docs)[0]["id"] == "a"
    assert rank("量子计算", docs) == []
    assert select_roles(Project.model_validate(project_data()).model_dump(), "subtitle")[0] == []


def test_knowledge_approval_retire_invalidation(system):
    c, f, h = system
    with f() as db:
        create(db, "source", "curation", {"title": "史料测试", "url": "https://example.org/test", "edition": "test",
               "kind": "PRIMARY_RECORD", "rights_status": "PUBLIC_DOMAIN"}, "src")
        create(
            db,
            "passage",
            "curation",
            {"source_id": "src", "content": "赤兔", "locator": "卷七", "text_hash": digest("赤兔")},
            "pass",
        )
        create(
            db,
            "claim",
            "curation",
            {
                "text": "赤兔 吕布",
                "source_id": "src",
                "passage_id": "pass",
                "passage_version": 1,
                "source_version": 1,
                "horse_id": "chitu",
                "epistemic_status": "ATTESTED",
                "review_state": "DRAFT",
                "evidence_strength": "MODERATE",
                "relation": "SUPPORTS",
            },
            "claim",
        )
        db.commit()
    assert c.get("/api/v2/search?q=赤兔").json()["mode"] == "INSUFFICIENT_EVIDENCE"

    assert c.post("/api/v2/admin/claims/claim/approve", headers=h["alice"]).status_code == 403
    approved = c.post("/api/v2/admin/claims/claim/approve", headers=h["admin"]).json()
    assert approved["version"] == 2
    assert c.get("/api/v2/search?q=赤兔").json()["mode"] == "RETRIEVAL_ONLY"
    p = new_project(c, h)
    data = p["data"]
    data["scenes"][0].update(label="ATTESTED", claim_refs=["claim@2"])
    c.patch(
        "/api/v2/projects/" + p["id"] + "/revisions", headers=h["alice"], json={"expected_version": 1, "project": data}
    )
    c.post("/api/v2/admin/claims/claim/retire", headers=h["admin"])
    assert c.get("/api/v2/projects/" + p["id"], headers=h["alice"]).json()["data"]["review_state"] == "NEEDS_REVIEW"
    assert c.get("/api/v2/search?q=赤兔").json()["mode"] == "INSUFFICIENT_EVIDENCE"


def test_curator_creates_source_and_revision_governance(system):
    c, f, h = system
    s = c.post(
        "/api/v2/admin/sources",
        headers=h["staff"],
        json={
            "title": "本地编辑测试来源",
            "url": "https://example.org/source",
            "kind": "EDITORIAL",
            "rights_status": "PUBLIC_DOMAIN",
        },
    )
    assert s.status_code == 201
    passage = c.post(
        "/api/v2/admin/passages",
        headers=h["staff"],
        json={"source_id": s.json()["id"], "locator": "第一段", "content": "测试原文，不是实际史料。"},
    )
    assert passage.status_code == 201
    data = {
        "text": "测试草稿",
        "source_id": s.json()["id"],
        "passage_id": passage.json()["id"],
        "passage_version": 1,
        "epistemic_status": "EDITORIAL",
        "evidence_strength": "WEAK",
    }
    claim = c.post("/api/v2/admin/claims", headers=h["staff"], json=data).json()
    data["text"] = "经过编辑的草稿"
    changed = c.patch(
        "/api/v2/admin/claims/" + claim["id"], headers=h["staff"], json={"expected_version": 1, "claim": data}
    )
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert (
        c.patch(
            "/api/v2/admin/claims/" + claim["id"], headers=h["staff"], json={"expected_version": 1, "claim": data}
        ).status_code
        == 409
    )
    assert (
        c.get("/api/v2/sources/" + s.json()["id"] + "/passages/" + passage.json()["id"]).json()["data"]["content"]
        == "测试原文，不是实际史料。"
    )
