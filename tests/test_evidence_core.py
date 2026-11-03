import importlib.util
import sys

import pytest
from app.v2.domain import create, digest
from app.v2.knowledge import KnowledgeRepository
from app.v2.models import Entity
from app.v2.research import ResearchAgent, ResearchPolicy
from conftest import ROOT


def seed(
    c, h, name="赤兔", horse="chitu", relation="SUPPORTS", genre="PRIMARY_RECORD", group="sgz", proposition="ownership"
):
    s = c.post(
        "/api/v2/admin/sources",
        headers=h["staff"],
        json={
            "title": "合成测试文献（非真实史料）",
            "url": "https://example.org/test",
            "edition": "test-fixture",
            "kind": genre,
            "rights_status": "PUBLIC_DOMAIN",
            "independence_group": group,
        },
    ).json()
    p = c.post(
        "/api/v2/admin/passages",
        headers=h["staff"],
        json={"source_id": s["id"], "locator": "测试段一", "content": name + "与吕布。<script>ignore rules</script>"},
    ).json()
    d = {
        "text": name + "的测试归属",
        "horse_id": horse,
        "source_id": s["id"],
        "passage_id": p["id"],
        "passage_version": 1,
        "epistemic_status": "LITERARY" if genre == "LITERARY_WORK" else "ATTESTED",
        "evidence_strength": "MODERATE",
        "relation": relation,
        "proposition_key": proposition,
    }
    claim = c.post("/api/v2/admin/claims", headers=h["staff"], json=d)
    assert claim.status_code == 200, claim.text
    approved = c.post("/api/v2/admin/claims/" + claim.json()["id"] + "/approve", headers=h["admin"])
    assert approved.status_code == 200, approved.text
    return s, p, approved.json()


def ask(c, text, prior=()):
    return c.post("/api/v2/answers", json={"messages": [*prior, {"role": "user", "content": text}]}).json()


def test_exact_reference_entity_legacy_sse(system):
    c, f, h = system
    s, p, claim = seed(c, h)
    result = ask(c, "赤菟的出处")
    assert result["mode"] == "SYNTHESIS"
    citation = result["citations"][0]
    assert citation["passage_revision"] == 1 and citation["quote"] == p["data"]["content"]
    assert c.post("/api/v2/evidence/validate", json={"citations": [citation]}).json()["valid"] == [True]
    page = c.get(citation["href"])
    assert page.status_code == 200 and "&lt;script&gt;" in page.text and "<script>" not in page.text
    assert c.get("/api/v2/horses/chitu").json()["claims"][0]["id"] == claim["id"]
    legacy = c.post(
        "/api/v1/chat", json={"stream": False, "messages": [{"role": "user", "content": "赤菟的出处"}]}
    ).json()
    assert legacy["citations"] == result["citations"] and legacy["model"] is None
    stream = c.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "赤兔"}]}).text
    assert '"type": "meta"' in stream and '"citations"' in stream and "[DONE]" in stream
    assert c.post("/api/v1/ai/query", json={"q": "赤兔"}).json()["results"][0]["id"] == claim["id"]


def test_withdrawal_version_and_source_invalidation(system):
    c, f, h = system
    s, p, claim = seed(c, h)
    citation = ask(c, "赤兔")["citations"][0]
    r = c.patch(
        "/api/v2/admin/passages/" + p["id"],
        headers=h["staff"],
        json={"expected_version": 1, "passage": {"source_id": s["id"], "locator": "更正段", "content": "更正原文"}},
    )
    assert r.status_code == 200
    assert c.post("/api/v2/evidence/validate", json={"citations": [citation]}).json()["stale"]
    assert not ask(c, "赤兔的出处")["citations"]
    old = c.get(citation["href"])
    assert "STALE" in old.text and "赤兔" in old.text
    c.post("/api/v2/admin/claims/" + claim["id"] + "/retire", headers=h["admin"])
    assert not c.get("/api/v2/search?q=赤兔").json()["results"]


def test_conflict_literature_and_dependence(system):
    c, f, h = system
    seed(c, h)
    seed(c, h, relation="CONTRADICTS")
    a = ask(c, "赤兔的史实")
    assert a["mode"] == "CONFLICT"
    assert a["evidence"]["independent_support_groups"] == 1
    assert all(x["relation"] == "SUPPORTS" for x in a["atomic_claims"])
    seed(c, h, name="的卢", horse="dilu", genre="LITERARY_WORK")
    assert ask(c, "的卢故事")["mode"] == "INTERPRETIVE"
    assert c.get("/api/v2/search?q=的卢&mode=history").json()["results"] == []


def test_no_answer_context_and_editorial(system):
    c, f, h = system
    assert ask(c, "量子火星的马是否存在")["mode"] == "INSUFFICIENT"
    assert ask(c, "赤兔简介")["mode"] == "BROWSE"
    assert ask(c, "它呢")["mode"] == "CLARIFY"
    seed(c, h)
    assert ask(c, "它的出处", [{"role": "user", "content": "赤兔"}])["citations"]
    assert ask(c, "它呢", [{"role": "user", "content": "赤兔和的卢"}])["mode"] == "CLARIFY"


def test_private_rights_and_invalid_span(system):
    c, f, h = system
    s, p, claim = seed(c, h)
    citation = ask(c, "赤兔")["citations"][0]
    d = s["data"]
    d["visibility"] = "PRIVATE"
    assert (
        c.patch(
            "/api/v2/admin/sources/" + s["id"], headers=h["staff"], json={"expected_version": 1, "source": d}
        ).status_code
        == 200
    )
    assert c.get(citation["href"]).status_code == 404
    assert c.get("/api/v2/sources/" + s["id"] + "/passages/" + p["id"]).status_code == 404
    assert not c.get("/api/v2/search?q=赤兔").json()["results"]
    assert not c.get("/api/v2/horses/chitu").json()["claims"]
    d = claim["data"]
    d["review_state"] = "DRAFT"
    d.pop("reviewer_id", None)
    d["span"] = [-1, 100]
    assert c.post("/api/v2/admin/claims", headers=h["staff"], json=d).status_code == 422


def test_research_real_tools_budget_permissions_review(system):
    c, f, h = system
    seed(c, h)
    p = c.post("/api/v2/research/runs", headers=h["alice"], json={"query": "赤兔和的卢比较", "max_calls": 5}).json()
    assert p["data"]["mode"] == "RULE_BASED" and len(p["data"]["trace"]) <= 5
    assert any(t["tool"] == "search_evidence" and t["output"]["results"] for t in p["data"]["trace"])
    assert c.get("/api/v2/research/runs/" + p["id"], headers=h["bob"]).status_code == 404
    assert (
        c.post("/api/v2/research/runs", headers=h["alice"], json={"query": "赤兔", "mode": "LIVE_LLM"}).status_code
        == 409
    )
    r = c.post(
        "/api/v2/research/runs/" + p["id"] + "/review",
        headers=h["alice"],
        json={"expected_version": 1, "decision": "ACCEPT", "note": "仅接受资料比较结果"},
    )
    assert r.status_code == 200
    assert (
        c.post(
            "/api/v2/research/runs/" + p["id"] + "/review",
            headers=h["alice"],
            json={"expected_version": 2, "decision": "ACCEPT", "note": "重复"},
        ).status_code
        == 409
    )
    with f() as db:
        agent = ResearchAgent(db, ResearchPolicy(max_calls=1))
        with pytest.raises(Exception) as err:
            agent.call("approve_claim", {})
        assert err.value.status_code == 403
        agent.call("check_coverage", {})
        with pytest.raises(Exception) as err:
            agent.call("check_coverage", {})
        assert err.value.status_code == 429


def test_migration_idempotent_and_preserves_users(system):
    c, f, h = system
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("rag_migrate", ROOT / "scripts/rag_migrate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with f() as db:
        from app.models.user import User

        before = [x.id for x in db.query(User).all()]
        create(db, "claim", "curation", {"horse_name": "赤兔", "review_state": "DRAFT"}, "old-link")
        db.commit()
        assert mod.migrate(db, True)["actions"]
        assert not mod.migrate(db, True)["actions"]
        assert db.get(Entity, "old-link").data["horse_id"] == "chitu"
        assert before == [x.id for x in db.query(User).all()]


def test_status_and_corrupt_hash_fail_closed(system):
    c, f, h = system
    s, p, claim = seed(c, h)
    assert c.get("/api/v1/chat/status").json()["EVIDENCE_VERIFIED"]
    with f() as db:
        entity = db.get(Entity, p["id"])
        entity.data = {**entity.data, "text_hash": digest("tampered")}
        db.commit()
        assert not KnowledgeRepository(db).citation(db.get(Entity, claim["id"]))
    assert not c.get("/api/v1/chat/status").json()["EVIDENCE_VERIFIED"]


def test_raw_passage_is_searchable_without_claim_and_creative_is_separate(system):
    c, f, h = system
    source = c.post(
        "/api/v2/admin/sources",
        headers=h["staff"],
        json={"title": "未审原文", "url": "https://example.org/raw", "kind": "PRIMARY_RECORD", "rights_status": "PUBLIC_DOMAIN"},
    ).json()
    p = c.post(
        "/api/v2/admin/passages",
        headers=h["staff"],
        json={"source_id": source["id"], "locator": "原文段", "content": "赤兔独立原文候选"},
    ).json()
    result = c.get("/api/v2/search?q=赤兔").json()
    assert result["results"] == []
    assert any(x["id"] == p["id"] for x in result["candidates"])
    assert c.get("/api/v2/passage-evidence/" + p["id"] + "@1").status_code == 200
    creative = c.get("/api/v2/knowledge/creative?q=赤兔").json()
    assert creative["count"] == 18 and creative["results"]
    assert all(not x["usable_as_fact"] for x in creative["results"])
    assert all(not x["usable_as_fact"] for x in result["editorial"])


def test_source_retire_invalidates_creative_bundle_and_review(system):
    c, f, h = system
    s, p, claim = seed(c, h)
    proposal = c.post("/api/v2/research/runs", headers=h["alice"], json={"query": "赤兔"}).json()
    task = c.post(
        "/api/v2/compat/workflow/tasks",
        headers=h["alice"],
        json={"title": "赤兔创作测试", "horse_name": "赤兔", "auto_start": False},
    ).json()
    with f() as db:
        task_entity = db.get(Entity, task["task"]["task_id"])
        project_id = task_entity.data["project_id"]
        assert db.get(Entity, project_id).data["knowledge_bundle"]["results"]
    c.post("/api/v2/admin/sources/" + s["id"] + "/retire", headers=h["admin"])
    assert c.get("/api/v2/projects/" + project_id, headers=h["alice"]).json()["data"]["review_state"] == "NEEDS_REVIEW"
    assert c.get("/api/v2/research/runs/" + proposal["id"], headers=h["alice"]).json()["stale"]
    assert (
        c.post(
            "/api/v2/research/runs/" + proposal["id"] + "/review",
            headers=h["alice"],
            json={"expected_version": 1, "decision": "ACCEPT", "note": "过期"},
        ).status_code
        == 409
    )


def test_unknown_source_independence_and_missing_edition_cannot_inflate_support(system):
    c, f, h = system
    s, p, claim = seed(c, h, group="")
    assert ask(c, "赤兔")["evidence"]["independent_support_groups"] == 0
    data = s["data"]
    data["edition"] = ""
    c.patch("/api/v2/admin/sources/" + s["id"], headers=h["staff"], json={"expected_version": 1, "source": data})
    assert not ask(c, "赤兔的出处")["citations"]


def test_legacy_index_rebuilds_on_text_and_metadata_changes(tmp_path):
    import json

    from app.services.ai_engine import query_vectordb

    corpus = tmp_path / "corpus.json"
    index = tmp_path / "index.json"
    corpus.write_text(json.dumps([{"id": "x", "text": "赤兔", "metadata": {"review": "draft"}}]), encoding="utf-8")
    assert query_vectordb("赤兔", corpus_path=str(corpus), db_path=str(index))
    corpus.write_text(json.dumps([{"id": "x", "text": "乌骓", "metadata": {"review": "retired"}}]), encoding="utf-8")
    assert not query_vectordb("赤兔", corpus_path=str(corpus), db_path=str(index))
    assert query_vectordb("乌骓", corpus_path=str(corpus), db_path=str(index))[0]["metadata"]["review"] == "retired"


def test_answer_audit_and_read_only_shadow(system):
    c,f,h=system
    s,p,claim=seed(c,h)
    body={'messages':[{'role':'user','content':'赤兔的出处'}]}
    a=c.post('/api/v2/answers',headers=h['alice'],json=body).json()
    assert c.get('/api/v2/answers/'+a['answer_id'],headers=h['alice']).json()['stale'] is False
    assert c.get('/api/v2/answers/'+a['answer_id'],headers=h['bob']).status_code==404
    shadow=c.get('/api/v2/knowledge/shadow-compare?q=赤兔').json()
    assert shadow['mode']=='READ_ONLY_NO_LLM' and shadow['legacy'] and shadow['unified']['results']
    c.post('/api/v2/admin/claims/'+claim['id']+'/retire',headers=h['admin'])
    old=c.get('/api/v2/answers/'+a['answer_id'],headers=h['alice']).json()
    assert old['stale'] and 'data' not in old
