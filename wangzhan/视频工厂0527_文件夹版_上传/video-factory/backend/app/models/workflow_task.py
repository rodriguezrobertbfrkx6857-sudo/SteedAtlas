from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    horse_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_node: Mapped[str | None] = mapped_column(String(80), nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="9:16")
    duration: Mapped[int] = mapped_column(Integer, default=30)
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    n8n_execution_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    callback_token: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    workflow_definition: Mapped[dict] = mapped_column(JSON, default=dict)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    normalized_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    node_states: Mapped[list] = mapped_column(JSON, default=list)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    dispatch_response: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
