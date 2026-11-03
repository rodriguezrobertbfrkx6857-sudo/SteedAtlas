from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CrossborderPublishRecord(Base):
    __tablename__ = "crossborder_publish_records"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(50), ForeignKey("products.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    marketplace: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="preview")
    status: Mapped[str] = mapped_column(String(30), default="prepared")
    locale: Mapped[str] = mapped_column(String(20), default="")
    currency: Mapped[str] = mapped_column(String(10), default="")
    shop_id: Mapped[int | None] = mapped_column(nullable=True)
    listing_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    marketplace_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    request_path: Mapped[str | None] = mapped_column(String(120), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_by_user_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
