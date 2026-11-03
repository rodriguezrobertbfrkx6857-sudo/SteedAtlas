"""Add Shopee connections table

Revision ID: f2a4b6c1d930
Revises: e18f9b6d2a11
Create Date: 2026-04-20 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a4b6c1d930"
down_revision: Union[str, None] = "e18f9b6d2a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shopee_connections",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("marketplace", sa.String(length=100), nullable=False),
        sa.Column("partner_id", sa.String(length=50), nullable=True),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_request_id", sa.String(length=100), nullable=True),
        sa.Column("connected_by_user_id", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["connected_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "shop_id", name="uq_shopee_connection_platform_shop"),
    )


def downgrade() -> None:
    op.drop_table("shopee_connections")
