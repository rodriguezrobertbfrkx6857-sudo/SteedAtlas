"""Add video tasks table

Revision ID: 4a19e7f6c3ab
Revises: 8b923d6c8edc
Create Date: 2026-04-19 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4a19e7f6c3ab"
down_revision: Union[str, None] = "8b923d6c8edc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "video_tasks",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("horse_id", sa.String(length=50), nullable=True),
        sa.Column("horse_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("visual_style", sa.String(length=30), nullable=True),
        sa.Column("script_style", sa.String(length=30), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("music", sa.String(length=30), nullable=True),
        sa.Column("narration", sa.Boolean(), nullable=True),
        sa.Column("voice", sa.String(length=100), nullable=True),
        sa.Column("custom_text", sa.Text(), nullable=True),
        sa.Column("estimated_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("script_payload", sa.JSON(), nullable=True),
        sa.Column("tts_payload", sa.JSON(), nullable=True),
        sa.Column("compose_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_video_tasks_horse_name"), "video_tasks", ["horse_name"], unique=False)
    op.create_index(op.f("ix_video_tasks_status"), "video_tasks", ["status"], unique=False)
    op.create_index(op.f("ix_video_tasks_user_id"), "video_tasks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_video_tasks_user_id"), table_name="video_tasks")
    op.drop_index(op.f("ix_video_tasks_status"), table_name="video_tasks")
    op.drop_index(op.f("ix_video_tasks_horse_name"), table_name="video_tasks")
    op.drop_table("video_tasks")
