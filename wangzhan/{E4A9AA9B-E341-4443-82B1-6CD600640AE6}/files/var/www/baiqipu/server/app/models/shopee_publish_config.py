from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ShopeePublishConfig(Base):
    __tablename__ = "shopee_publish_configs"
    __table_args__ = (UniqueConstraint("platform", name="uq_shopee_publish_config_platform"),)

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    marketplace: Mapped[str] = mapped_column(String(100), nullable=False)
    shop_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_logistic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_options_json: Mapped[str] = mapped_column(Text, default="[]")
    logistic_options_json: Mapped[str] = mapped_column(Text, default="[]")
    default_weight_kg: Mapped[float] = mapped_column(Float, default=0.35)
    item_status: Mapped[str] = mapped_column(String(20), default="UNLIST")
    upload_images: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_by_user_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
