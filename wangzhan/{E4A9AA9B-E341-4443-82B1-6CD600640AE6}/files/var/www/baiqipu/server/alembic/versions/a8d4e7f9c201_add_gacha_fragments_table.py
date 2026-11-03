"""Add gacha fragments table

Revision ID: a8d4e7f9c201
Revises: 7a6b5c4d3e2f
Create Date: 2026-04-29 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8d4e7f9c201"
down_revision: Union[str, None] = "7a6b5c4d3e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gacha_fragments",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("horse_id", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["horse_id"], ["horses.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "horse_id", name="uq_gacha_fragments_user_horse"),
    )
    op.create_index(op.f("ix_gacha_fragments_horse_id"), "gacha_fragments", ["horse_id"], unique=False)
    op.create_index(op.f("ix_gacha_fragments_user_id"), "gacha_fragments", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_gacha_fragments_user_id"), table_name="gacha_fragments")
    op.drop_index(op.f("ix_gacha_fragments_horse_id"), table_name="gacha_fragments")
    op.drop_table("gacha_fragments")
