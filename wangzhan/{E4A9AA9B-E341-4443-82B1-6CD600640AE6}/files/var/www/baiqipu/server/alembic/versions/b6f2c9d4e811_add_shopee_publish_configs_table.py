"""Add shopee publish configs table

Revision ID: b6f2c9d4e811
Revises: 9d3f0b7c4e21
Create Date: 2026-04-20 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b6f2c9d4e811"
down_revision: Union[str, None] = "9d3f0b7c4e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shopee_publish_configs",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("marketplace", sa.String(length=100), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=True),
        sa.Column("default_category_id", sa.Integer(), nullable=True),
        sa.Column("default_logistic_id", sa.Integer(), nullable=True),
        sa.Column("default_weight_kg", sa.Float(), nullable=False),
        sa.Column("item_status", sa.String(length=20), nullable=False),
        sa.Column("upload_images", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", name="uq_shopee_publish_config_platform"),
    )


def downgrade() -> None:
    op.drop_table("shopee_publish_configs")
