from datetime import date, datetime

from sqlalchemy import String, DateTime, Integer, Date, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=True)
    wechat_openid: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user / operator / admin
    tier: Mapped[str] = mapped_column(String(20), default="new")  # new / growing / collector
    purchase_count: Mapped[int] = mapped_column(Integer, default=0)
    checkin_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_checkins: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
