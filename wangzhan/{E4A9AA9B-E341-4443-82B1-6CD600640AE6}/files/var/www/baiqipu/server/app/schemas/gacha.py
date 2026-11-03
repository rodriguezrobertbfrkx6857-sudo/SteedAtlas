from datetime import date, datetime

from pydantic import BaseModel, Field


class GachaDrawRequest(BaseModel):
    draw_type: str = "single"  # single / ten / free
    pool_id: str | None = None
    up_horse_id: str | None = None


class GachaResultItem(BaseModel):
    horse_id: str
    horse_name: str
    rarity: str
    is_new: bool
    is_pity: bool = False
    is_up: bool = False
    fragments_awarded: int = 0


class GachaFragmentItem(BaseModel):
    horse_id: str
    horse_name: str
    rarity: str
    quantity: int = 0
    redeem_cost: int = 0


class GachaDrawResult(BaseModel):
    results: list[GachaResultItem]
    pity_count: int
    collection_progress: dict = Field(default_factory=dict)
    new_achievements: list[dict] = Field(default_factory=list)
    fragments: list[GachaFragmentItem] = Field(default_factory=list)


class CollectionItem(BaseModel):
    horse_id: str
    horse_name: str
    rarity: str
    source: str
    obtained_at: datetime

    model_config = {"from_attributes": True}


class CollectionOut(BaseModel):
    owned_horses: list[CollectionItem]
    progress: dict
    achievements: list[dict]
    pity_count: int
    fragments: list[GachaFragmentItem] = Field(default_factory=list)


class GachaFragmentsOut(BaseModel):
    fragments: list[GachaFragmentItem] = Field(default_factory=list)


class GachaExchangeRequest(BaseModel):
    horse_id: str


class GachaExchangeOut(BaseModel):
    owned_horses: list[CollectionItem]
    progress: dict
    pity_count: int
    fragments: list[GachaFragmentItem] = Field(default_factory=list)
    message: str


class CheckinRewardOut(BaseModel):
    day: int
    reward: str
    reward_type: str


class CheckinStatusOut(BaseModel):
    streak: int = 0
    total_checkins: int = 0
    last_checkin_date: date | None = None
    checked_today: bool = False
    completed_cycle_days: int = 0
    next_cycle_day: int = 1
    rewards: list[CheckinRewardOut] = Field(default_factory=list)
    next_reward: CheckinRewardOut | None = None


class CheckinActionOut(BaseModel):
    status: CheckinStatusOut
    reward: CheckinRewardOut | None = None
    just_checked: bool = False
    message: str


class LeaderboardEntryOut(BaseModel):
    rank: int
    user_id: str
    nickname: str
    avatar: str
    total_owned: int = 0
    ssr_count: int = 0
    total_draws: int = 0
    checkin_streak: int = 0
    total_checkins: int = 0
    is_current_user: bool = False


class LeaderboardOut(BaseModel):
    updated_at: datetime
    limit: int = 10
    items: list[LeaderboardEntryOut] = Field(default_factory=list)
    current_user_rank: LeaderboardEntryOut | None = None
