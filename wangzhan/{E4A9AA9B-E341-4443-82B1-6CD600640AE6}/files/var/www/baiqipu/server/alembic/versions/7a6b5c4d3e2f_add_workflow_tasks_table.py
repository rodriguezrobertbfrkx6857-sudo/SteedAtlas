"""Add workflow tasks table

Revision ID: 7a6b5c4d3e2f
Revises: 3ed180ed1ff6
Create Date: 2026-04-27 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a6b5c4d3e2f"
down_revision: Union[str, None] = "3ed180ed1ff6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_tasks",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("horse_name", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("current_node", sa.String(length=80), nullable=True),
        sa.Column("aspect_ratio", sa.String(length=20), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
        sa.Column("n8n_execution_id", sa.String(length=120), nullable=True),
        sa.Column("callback_token", sa.String(length=120), nullable=False),
        sa.Column("workflow_definition", sa.JSON(), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("normalized_payload", sa.JSON(), nullable=True),
        sa.Column("node_states", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("dispatch_response", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_tasks_callback_token"), "workflow_tasks", ["callback_token"], unique=False)
    op.create_index(op.f("ix_workflow_tasks_horse_name"), "workflow_tasks", ["horse_name"], unique=False)
    op.create_index(op.f("ix_workflow_tasks_status"), "workflow_tasks", ["status"], unique=False)
    op.create_index(op.f("ix_workflow_tasks_user_id"), "workflow_tasks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_tasks_user_id"), table_name="workflow_tasks")
    op.drop_index(op.f("ix_workflow_tasks_status"), table_name="workflow_tasks")
    op.drop_index(op.f("ix_workflow_tasks_horse_name"), table_name="workflow_tasks")
    op.drop_index(op.f("ix_workflow_tasks_callback_token"), table_name="workflow_tasks")
    op.drop_table("workflow_tasks")
