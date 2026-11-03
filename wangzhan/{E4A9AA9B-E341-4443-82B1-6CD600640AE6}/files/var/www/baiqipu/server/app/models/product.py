from sqlalchemy import String, Text, Float, Integer, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    horse_id: Mapped[str] = mapped_column(String(50), ForeignKey("horses.id"), nullable=False)
    series: Mapped[str] = mapped_column(String(100), default="")
    price: Mapped[float] = mapped_column(Float, nullable=False)
    original_price: Mapped[float] = mapped_column(Float, nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=500)
    limited_edition: Mapped[bool] = mapped_column(Boolean, default=False)
    limited_count: Mapped[int] = mapped_column(Integer, nullable=True)
    images: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    emotional_points: Mapped[list] = mapped_column(JSON, default=list)
    translations: Mapped[dict] = mapped_column(JSON, default=dict)
