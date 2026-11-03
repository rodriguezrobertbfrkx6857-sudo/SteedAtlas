from pydantic import BaseModel, Field, field_validator


class ProductOut(BaseModel):
    id: str
    name: str
    horse_id: str
    series: str = ""
    price: float
    original_price: float | None = None
    stock: int = 0
    limited_edition: bool = False
    limited_count: int | None = None
    images: list[str] = Field(default_factory=list)
    description: str = ""
    specs: dict = Field(default_factory=dict)
    emotional_points: list[str] = Field(default_factory=list)
    translations: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}

    @field_validator("series", "description", mode="before")
    @classmethod
    def default_empty_string(cls, value):
        return "" if value is None else value

    @field_validator("images", "emotional_points", mode="before")
    @classmethod
    def default_empty_list(cls, value):
        return [] if value is None else value

    @field_validator("specs", "translations", mode="before")
    @classmethod
    def default_empty_dict(cls, value):
        return {} if value is None else value


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int
