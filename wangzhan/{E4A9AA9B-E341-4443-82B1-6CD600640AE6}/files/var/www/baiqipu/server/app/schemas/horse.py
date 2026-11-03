from pydantic import BaseModel


class HorseOut(BaseModel):
    id: str
    name: str
    title: str
    rarity: str
    image: str
    story: str
    full_story: str = ""
    historical_source: str = ""
    dynasty: str = ""
    owner: str = ""
    trait: str
    traits: list[str] = []
    drop_rate: float = 0.0
    price: float | None = None

    model_config = {"from_attributes": True}


class HorseListOut(BaseModel):
    items: list[HorseOut]
    total: int
