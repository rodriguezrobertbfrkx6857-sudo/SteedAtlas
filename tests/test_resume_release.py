"""Application integration boundaries; all historical fixtures are synthetic."""

import pytest
from app.v2.knowledge import EvidenceSearch, KnowledgeRepository
from app.v2.models import Entity
from test_autonomous_sources import ingest
from test_evidence_core import ask, seed


def test_saturated_topk_keeps_opposition_and_reports_truncation(system):
    client, factory, headers = system
    for _ in range(3):
        seed(client, headers)
    _, _, opposing = seed(client, headers, name="异文", relation="CONTRADICTS")
    with factory() as db:
        result = EvidenceSearch(KnowledgeRepository(db)).search("赤兔归属", limit=2)
        assert len(result["results"]) == 2
        assert opposing["id"] in {h["id"] for h in result["results"]}
        small = EvidenceSearch(KnowledgeRepository(db)).search("赤兔归属", limit=1)
        assert small["coverage"]["opposition_truncated"]


def test_entity_limit_and_candidate_scope(system):
    client, factory, headers = system
    seed(client, headers)
    seed(client, headers, name="的卢", horse="dilu", genre="LITERARY_WORK")
    with factory() as db:
        result = EvidenceSearch(KnowledgeRepository(db)).search("赤兔和的卢", "all", 1)
        assert len(result["results"]) == 1
        assert result["coverage"]["missing_entity_ids"]
        historical = EvidenceSearch(KnowledgeRepository(db)).search("赤兔和的卢", "history", 8)
        assert all(h["genre"] != "LITERARY_WORK" for h in historical["candidates"])


def test_mixed_intent_and_unsupported_date(system):
    client, factory, _ = system
    with factory() as db:
        ingest(db)
    assert ask(client, "给我讲赤兔故事，但先列原文")["mode"] == "SOURCE_ATTRIBUTED"
    result = ask(client, "赤兔出生于哪年哪月哪日？")
    assert result["mode"] == "INSUFFICIENT"
    assert "不能" in result["message"]
    assert ask(client, "我重视责任和守护，哪匹马适合我？")["mode"] == "CULTURE"


@pytest.mark.parametrize("failure", [TimeoutError, RuntimeError])
def test_actual_agent_failure_trace_and_cleanup(system, monkeypatch, failure):
    from app.v2.research import ResearchAgent

    _, factory, _ = system

    class Provider:
        closed = False

        def close(self):
            self.closed = True
            raise ValueError("cleanup")

    with factory() as db:
        agent = ResearchAgent(db)
        provider = agent.provider = Provider()

        def fail(*args):
            raise failure("primary")

        monkeypatch.setattr(agent.repo, "entities", fail)
        with pytest.raises(failure, match="primary"):
            agent.run("赤兔")
        assert provider.closed and agent.provider is None
        assert agent.trace[-1]["status"] == "FAILED"


@pytest.mark.parametrize("restriction", ["expired", "network", "rights", "private", "withdrawn", "hash"])
def test_snapshot_policy_separates_freshness_from_integrity(system, restriction):
    from datetime import datetime, timedelta, timezone

    client, factory, _ = system
    with factory() as db:
        repo, claim, _ = ingest(db)
        source = repo.rows[claim.data["source_id"]]
        health = db.get(Entity, source.id + "-health")
        health.data = {**health.data, "checked_at": (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()}
        if restriction == "network":
            health.data = {**health.data, "status": "TEMPORARY_NETWORK_ERROR"}
        elif restriction in ("rights", "private", "withdrawn", "hash"):
            key, value = {
                "rights": ("rights_state", "RESTRICTED"),
                "private": ("visibility", "PRIVATE"),
                "withdrawn": ("review_state", "RETIRED"),
                "hash": ("document_hash", "wrong"),
            }[restriction]
            source.data = {**source.data, key: value}
        db.commit()
        assert KnowledgeRepository(db).citation(claim) is None
        snapshot = KnowledgeRepository(db, snapshot_only=True).citation(claim)
        assert bool(snapshot) == (restriction in ("expired", "network"))
        response = client.get("/api/v2/snapshot-evidence/" + claim.id)
        assert response.status_code == (200 if snapshot else 404)
        if snapshot:
            assert "非实时" in response.text and "最后成功观察" in response.text


def test_acquisition_quotas_persist_and_release(tmp_path):
    from app.v2.acquisition_limits import acquisition_slot
    from fastapi import HTTPException

    path = tmp_path / "quota.db"
    with acquisition_slot(path, "alice"):
        with pytest.raises(HTTPException, match="BUSY"):
            with acquisition_slot(path, "bob"):
                pass
    for _ in range(2):
        with acquisition_slot(path, "alice"):
            pass
    with pytest.raises(HTTPException, match="QUOTA"):
        with acquisition_slot(path, "alice"):
            pass
    for i in range(9):
        with acquisition_slot(path, str(i)):
            pass
    with pytest.raises(HTTPException, match="QUOTA"):
        with acquisition_slot(path, "new-user"):
            pass


def test_unknown_proposition_or_other_entity_never_conflict(system):
    client, factory, headers = system
    seed(client, headers, proposition="")
    seed(client, headers, name="的卢", horse="dilu", relation="CONTRADICTS", proposition="")
    with factory() as db:
        bundle = EvidenceSearch(KnowledgeRepository(db)).search("赤兔和的卢", "all", 3)
        assert bundle["coverage"]["known_opposition_pairs"] == 0
    assert ask(client, "赤兔和的卢的史籍")["mode"] != "CONFLICT"


def test_cached_replay_cannot_erase_newer_restriction(system):
    from app.v2.source_acquisition import mark_unavailable
    from test_autonomous_sources import document

    client, factory, _ = system
    with factory() as db:
        doc = document()
        repo, claim, _ = ingest(db, doc)
        href = repo.citation(claim)["href"]
        mark_unavailable(db, doc["title"], "QUARANTINED_SITE_LICENSE_CHANGED")
        ingest(db, doc)
        assert KnowledgeRepository(db).citation(claim) is None
        assert KnowledgeRepository(db, snapshot_only=True).citation(claim) is None
        assert client.get(href).status_code == 404


def test_no_source_original_text_refuses_editorial_and_sse_has_summary(system):
    client, factory, _ = system
    assert ask(client, "赤兔原文")["mode"] == "INSUFFICIENT"
    with factory() as db:
        ingest(db)
    response = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "赤兔原文"}]}).text
    assert '"summary"' in response


def test_same_spelling_in_another_novel_not_same_catalogue_identity():
    from app.v2.source_acquisition import link_alias

    horse = {"id": "h015", "name": "白龙马"}
    assert link_alias(horse, "白龍馬載三藏。", "西遊記/001") == "白龙马"
    assert link_alias(horse, "白龍馬騎者。", "隋唐演義/004") is None
