import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Scene(Strict):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,32}$")
    text: str = Field(max_length=240)
    duration_ticks: int = Field(default=72, ge=24, le=1440)
    asset_id: str | None = None
    claim_refs: list[str] = Field(default_factory=list, max_length=20)
    label: Literal[
        "ATTESTED",
        "LITERARY",
        "FOLKLORE",
        "EDITORIAL",
        "DISPUTED",
        "CREATIVE",
        "SOURCE_ATTRIBUTED",
        "LITERARY_ATTRIBUTED",
    ] = "CREATIVE"
    period: str = Field(default="", max_length=80)
    script_doc: dict | None = None

    @field_validator("claim_refs")
    @classmethod
    def typed_references(cls, values):
        if any(not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}@[1-9][0-9]{0,8}", v) for v in values):
            raise ValueError("Claim references require id@version")
        return values


class Project(Strict):
    title: str = Field(min_length=1, max_length=100)
    horse_id: str = Field(default="chitu", max_length=64)
    scenes: list[Scene] = Field(min_length=1, max_length=12)
    bible: dict[str, Annotated[str, Field(max_length=160)]] = Field(
        default_factory=lambda: {"style": "数字博物馆", "period": "", "identity": "赤兔"}, max_length=12
    )
    width: Literal[720, 1280, 1080, 1920] = 1280
    height: Literal[720, 1280, 1080, 1920] = 720
    fps_num: Literal[24, 25, 30] = 24
    fps_den: Literal[1] = 1
    audio_asset_ids: list[str] = Field(default_factory=list, max_length=2)
    audio_gain: float = Field(default=0.6, ge=0, le=2)
    audio_fade_seconds: float = Field(default=0.3, ge=0, le=3)
    review_state: Literal["DRAFT", "APPROVED", "NEEDS_REVIEW"] = "DRAFT"
    # Server recomputes this on create/save; clients may round-trip a project envelope.
    knowledge_bundle: dict = Field(default_factory=dict, max_length=12)

    @model_validator(mode="after")
    def validate_timeline(self):
        if len({s.id for s in self.scenes}) != len(self.scenes):
            raise ValueError("Duplicate scene IDs")
        if sum(s.duration_ticks for s in self.scenes) > self.fps_num * 180:
            raise ValueError("Preview limit: 180 seconds")
        if (self.width, self.height) not in {
            (1280, 720),
            (720, 1280),
            (1920, 1080),
            (1080, 1920),
            (1080, 1080),
        }:
            raise ValueError("Unsupported resolution preset")
        return self


class SaveProject(Strict):
    expected_version: int = Field(ge=1)
    project: Project


class ClaimInput(Strict):
    text: str = Field(min_length=1, max_length=1000)
    source_id: str
    passage_id: str
    passage_version: int = Field(ge=1)
    source_version: int | None = Field(default=None, ge=1)
    horse_id: str | None = Field(default=None, max_length=64)
    subject_entity_ids: list[str] = Field(default_factory=list, max_length=20)
    span: tuple[int, int] | None = None
    proposition_key: str = Field(default="", max_length=160)
    epistemic_status: Literal["ATTESTED", "LITERARY", "FOLKLORE", "EDITORIAL", "DISPUTED", "CREATIVE"]
    evidence_strength: Literal["NONE", "WEAK", "MODERATE", "STRONG"]
    relation: Literal["SUPPORTS", "CONTRADICTS", "MENTIONS", "INDETERMINATE"] = "SUPPORTS"
    review_state: Literal["DRAFT"] = "DRAFT"


class ClaimRevisionInput(Strict):
    expected_version: int = Field(ge=1)
    claim: ClaimInput


class SourceInput(Strict):
    title: str = Field(min_length=1, max_length=240)
    url: str = Field(pattern=r"^https://", max_length=1000)
    edition: str = Field(default="", max_length=240)
    language: str = Field(default="zh", max_length=20)
    kind: Literal["PRIMARY_RECORD", "SCHOLARLY", "LITERARY_WORK", "FOLK_TRADITION", "EDITORIAL", "GENERATED"]
    rights_status: Literal["UNKNOWN", "PUBLIC_DOMAIN", "LICENSED"] = "UNKNOWN"
    reliability: Literal["UNREVIEWED"] = "UNREVIEWED"
    independence_group: str = Field(default="", max_length=160)
    derived_from: list[str] = Field(default_factory=list, max_length=20)
    review_state: Literal["DRAFT"] = "DRAFT"
    visibility: Literal["PUBLIC", "PRIVATE"] = "PUBLIC"


class PassageInput(Strict):
    source_id: str
    locator: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="zh", max_length=20)
    subject_entity_ids: list[str] = Field(default_factory=list, max_length=20)


class ProposalRequest(Strict):
    intent: Literal["plan", "subtitle", "evidence", "repair"] = "plan"
    mode: Literal["RULE_BASED", "MANUAL", "LIVE_LLM", "MOCK_TEST"] = "RULE_BASED"
    expected_version: int = Field(ge=1)
    max_turns: int = Field(default=2, ge=1, le=3)


class ProposalReview(Strict):
    decision: Literal["ACCEPT", "REJECT"]
    expected_version: int = Field(ge=1)


class RenderRequest(Strict):
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=128)


class CompileRequest(Strict):
    expected_version: int | None = Field(default=None, ge=1)
