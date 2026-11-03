"""Tests for the agent provider truth layer.

The agent must never imply that a live model answered when none did.
"""

from app.v2 import agent_providers
from conftest import new_project


def test_catalogue_marks_live_llm_as_blocked():
    catalogue = agent_providers.catalogue()
    assert catalogue["live_provider_enabled"] is False
    modes = {item["mode"]: item for item in catalogue["modes"]}
    assert set(modes) == {"MANUAL", "RULE_BASED", "LIVE_LLM", "MOCK_TEST"}
    assert modes["LIVE_LLM"]["available"] is False
    assert modes["LIVE_LLM"]["truth_level"] == "blocked"
    assert modes["LIVE_LLM"]["deterministic"] is False
    assert agent_providers.BLOCKED_REASON in modes["LIVE_LLM"]["notes"]
    assert modes["RULE_BASED"]["truth_level"] == "deterministic_local_rules"
    assert modes["RULE_BASED"]["deterministic"] is True
    assert modes["MANUAL"]["truth_level"] == "human_decided"
    assert modes["MOCK_TEST"]["available"] is False


def test_capabilities_expose_the_truth_layer(system):
    c, f, h = system
    payload = c.get("/api/v2/capabilities", headers=h["alice"]).json()
    assert payload["agent_modes"] == ["MANUAL", "RULE_BASED"]
    assert payload["external_video"] is False
    assert payload["publication"] is False
    assert payload["agent_provider_catalogue"]["live_provider_enabled"] is False

    catalogue = c.get("/api/v2/agent-providers", headers=h["alice"]).json()
    live = next(item for item in catalogue["modes"] if item["mode"] == "LIVE_LLM")
    assert live["available"] is False
    assert agent_providers.BLOCKED_REASON in live["notes"]


def test_live_llm_request_is_refused_with_blocked_reason(system):
    c, f, h = system
    p = new_project(c, h)
    response = c.post(
        f"/api/v2/projects/{p['id']}/agent-runs",
        headers=h["alice"],
        json={"intent": "plan", "mode": "LIVE_LLM", "expected_version": p["version"], "max_turns": 2},
    )
    assert response.status_code == 409
    assert agent_providers.BLOCKED_REASON in response.json()["detail"]


def test_mock_test_request_is_refused(system):
    c, f, h = system
    p = new_project(c, h)
    response = c.post(
        f"/api/v2/projects/{p['id']}/agent-runs",
        headers=h["alice"],
        json={"intent": "plan", "mode": "MOCK_TEST", "expected_version": p["version"], "max_turns": 2},
    )
    assert response.status_code == 409


def test_rule_based_proposal_is_deterministic(system):
    c, f, h = system
    p = new_project(c, h)
    body = {"intent": "plan", "mode": "RULE_BASED", "expected_version": p["version"], "max_turns": 2}
    first = c.post(f"/api/v2/projects/{p['id']}/agent-runs", headers=h["alice"], json=body)
    assert first.status_code == 200, first.text
    second = c.post(f"/api/v2/projects/{p['id']}/agent-runs", headers=h["alice"], json=body)
    assert second.status_code == 200, second.text
    a = first.json()["data"]
    b = second.json()["data"]
    assert a["mode"] == "RULE_BASED"
    assert a["input_hash"] == b["input_hash"]
    assert a["tool_calls"] == b["tool_calls"]
    assert a["patches"] == b["patches"]


def test_manual_proposal_contains_no_patches(system):
    c, f, h = system
    p = new_project(c, h)
    response = c.post(
        f"/api/v2/projects/{p['id']}/agent-runs",
        headers=h["alice"],
        json={"intent": "plan", "mode": "MANUAL", "expected_version": p["version"], "max_turns": 2},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["patches"] == []
    assert response.json()["data"]["mode"] == "MANUAL"


def test_agent_cannot_self_approve(system):
    c, f, h = system
    p = new_project(c, h)
    proposal = c.post(
        f"/api/v2/projects/{p['id']}/agent-runs",
        headers=h["alice"],
        json={"intent": "plan", "mode": "RULE_BASED", "expected_version": p["version"], "max_turns": 2},
    ).json()
    identity = proposal["id"]
    review = c.post(
        f"/api/v2/agent-proposals/{identity}/review",
        headers=h["alice"],
        json={"decision": "ACCEPT", "expected_version": p["version"]},
    )
    assert review.status_code == 200, review.text
    # Accepting a proposal still leaves the project in DRAFT; a human must approve.
    after = c.get(f"/api/v2/projects/{p['id']}", headers=h["alice"]).json()
    assert after["data"]["review_state"] == "DRAFT"
    render = c.post(
        f"/api/v2/projects/{p['id']}/renders",
        headers=h["alice"],
        json={"expected_version": after["version"], "idempotency_key": "agent-should-not-render"},
    )
    assert render.status_code == 409
    assert "HUMAN_APPROVAL_REQUIRED" in render.json()["detail"]
