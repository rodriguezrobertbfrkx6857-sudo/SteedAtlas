from sqlalchemy import String, Text, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Horse(Base):
    __tablename__ = "horses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    rarity: Mapped[str] = mapped_column(String(10), nullable=False)  # SSR / SR / R
    image: Mapped[str] = mapped_column(String(500), nullable=False)
    story: Mapped[str] = mapped_column(Text, nullable=False)
    full_story: Mapped[str] = mapped_column(Text, default="")
    historical_source: Mapped[str] = mapped_column(String(200), default="")
    dynasty: Mapped[str] = mapped_column(String(50), default="")
    owner: Mapped[str] = mapped_column(String(100), default="")
    trait: Mapped[str] = mapped_column(String(100), nullable=False)
    traits: Mapped[list] = mapped_column(JSON, default=list)
    drop_rate: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, nullable=True)
