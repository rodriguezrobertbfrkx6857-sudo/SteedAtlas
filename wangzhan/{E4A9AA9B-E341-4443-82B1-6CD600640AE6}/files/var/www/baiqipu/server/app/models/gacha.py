from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GachaRecord(Base):
    __tablename__ = "gacha_records"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False)
    horse_id: Mapped[str] = mapped_column(String(50), ForeignKey("horses.id"), nullable=False)
    rarity: Mapped[str] = mapped_column(String(10), nullable=False)
    draw_type: Mapped[str] = mapped_column(String(20), nullable=False)  # free / single / ten
    pity_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False)
    horse_id: Mapped[str] = mapped_column(String(50), ForeignKey("horses.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="gacha")  # gacha / quiz / purchase
    obtained_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GachaFragment(Base):
    __tablename__ = "gacha_fragments"
    __table_args__ = (UniqueConstraint("user_id", "horse_id", name="uq_gacha_fragments_user_horse"),)

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    horse_id: Mapped[str] = mapped_column(String(50), ForeignKey("horses.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
