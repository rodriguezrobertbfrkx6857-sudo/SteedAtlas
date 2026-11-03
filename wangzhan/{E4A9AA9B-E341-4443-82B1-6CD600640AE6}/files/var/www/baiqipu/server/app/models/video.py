from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    horse_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    horse_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    visual_style: Mapped[str] = mapped_column(String(30), default="cinematic")
    script_style: Mapped[str] = mapped_column(String(30), default="emotional")
    duration: Mapped[int] = mapped_column(Integer, default=15)
    music: Mapped[str] = mapped_column(String(30), default="epic")
    narration: Mapped[bool] = mapped_column(Boolean, default=True)
    voice: Mapped[str] = mapped_column(String(100), default="zh-CN-XiaoxiaoNeural")
    custom_text: Mapped[str] = mapped_column(Text, default="")
    estimated_seconds: Mapped[int] = mapped_column(Integer, default=120)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    script_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    tts_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    compose_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
