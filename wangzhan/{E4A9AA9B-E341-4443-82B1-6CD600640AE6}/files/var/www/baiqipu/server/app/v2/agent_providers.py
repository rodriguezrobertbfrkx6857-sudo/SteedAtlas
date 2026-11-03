"""Agent provider registry with an explicit truth level for every mode.

The V2 agent must never overstate what it did. Each provider declares:

  * `human_decided`   - a human decides; the agent only records the decision
  * `deterministic_local_rules` - a rule-based planner runs locally
  * `blocked`         - a live external model would answer (not enabled here)

`LIVE_LLM` is implemented as a **skeleton** only: it has no credentials, no
network call, and refuses to produce a proposal. Any attempt to use it returns
`BLOCKED: LIVE NOT VERIFIED` so the audit trail can never claim a live model
was used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BLOCKED_REASON = "BLOCKED: LIVE NOT VERIFIED"


@dataclass(frozen=True)
class AgentProvider:
    mode: str
    truth_level: str
    description: str
    available: bool
    deterministic: bool
    produces_proposal: bool
    requires_approval: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)


PROVIDERS: dict[str, AgentProvider] = {
    "MANUAL": AgentProvider(
        mode="MANUAL",
        truth_level="human_decided",
        description="A human decides every change; the agent only records the decision and its reasons.",
        available=True,
        deterministic=True,
        produces_proposal=True,
        notes=("No model is involved.", "The proposal contains no patches."),
    ),
    "RULE_BASED": AgentProvider(
        mode="RULE_BASED",
        truth_level="deterministic_local_rules",
        description="A local rule engine inspects the timeline and proposes a bounded style patch.",
        available=True,
        deterministic=True,
        produces_proposal=True,
        notes=(
            "Runs locally; no network call and no credentials.",
            "Same project revision always yields the same proposal.",
            "Cannot grant approval or rewrite facts.",
        ),
    ),
    "LIVE_LLM": AgentProvider(
        mode="LIVE_LLM",
        truth_level="blocked",
        description="Reserved for a future external model provider.",
        available=False,
        deterministic=False,
        produces_proposal=False,
        notes=(
            BLOCKED_REASON,
            "No API key is configured in this environment.",
            "No request is sent to any external service.",
            "Requests are refused with HTTP 409 so no record can imply a live model answered.",
        ),
    ),
    "MOCK_TEST": AgentProvider(
        mode="MOCK_TEST",
        truth_level="test_only",
        description="Deterministic fixture used by the automated test suite.",
        available=False,
        deterministic=True,
        produces_proposal=False,
        notes=("Test-only. Refused outside the automated test harness.",),
    ),
}

# Modes the API accepts at runtime.
RUNTIME_MODES = ("MANUAL", "RULE_BASED")


def describe(mode: str) -> dict[str, Any]:
    provider = PROVIDERS.get(str(mode or "").upper())
    if not provider:
        return {
            "mode": str(mode or "").upper(),
            "truth_level": "unknown",
            "available": False,
            "description": "Unknown agent mode.",
            "notes": [],
        }
    return {
        "mode": provider.mode,
        "truth_level": provider.truth_level,
        "description": provider.description,
        "available": provider.available,
        "deterministic": provider.deterministic,
        "produces_proposal": provider.produces_proposal,
        "requires_approval": provider.requires_approval,
        "notes": list(provider.notes),
    }


def catalogue() -> dict[str, Any]:
    return {
        "modes": [describe(mode) for mode in sorted(PROVIDERS)],
        "runtime_modes": list(RUNTIME_MODES),
        "live_provider_enabled": False,
        "statement": (
            "本环境未接入任何外部大模型。RULE_BASED 为站内确定性规则引擎，MANUAL 由人工决策；"
            "LIVE_LLM 未开通，返回 BLOCKED: LIVE NOT VERIFIED。"
        ),
    }
