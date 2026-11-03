"""Add crossborder publish records table

Revision ID: 9d3f0b7c4e21
Revises: f2a4b6c1d930
Create Date: 2026-04-20 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d3f0b7c4e21"
down_revision: Union[str, None] = "f2a4b6c1d930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crossborder_publish_records",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("product_id", sa.String(length=50), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("marketplace", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=True),
        sa.Column("listing_id", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("marketplace_url", sa.String(length=500), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("request_path", sa.String(length=120), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_by_user_id", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("crossborder_publish_records")
