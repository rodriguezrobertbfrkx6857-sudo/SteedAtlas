from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ShopeeConnection(Base):
    __tablename__ = "shopee_connections"
    __table_args__ = (UniqueConstraint("platform", "shop_id", name="uq_shopee_connection_platform_shop"),)

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    marketplace: Mapped[str] = mapped_column(String(100), nullable=False)
    partner_id: Mapped[str] = mapped_column(String(50), default="")
    shop_id: Mapped[int] = mapped_column(Integer, nullable=False)
    merchant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_request_id: Mapped[str] = mapped_column(String(100), default="")
    connected_by_user_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
