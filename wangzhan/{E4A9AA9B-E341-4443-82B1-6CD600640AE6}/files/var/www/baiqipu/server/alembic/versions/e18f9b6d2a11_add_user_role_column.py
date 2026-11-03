"""Add user role column

Revision ID: e18f9b6d2a11
Revises: c4a8e6a95bb1
Create Date: 2026-04-20 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e18f9b6d2a11"
down_revision: Union[str, None] = "c4a8e6a95bb1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=20), nullable=True, server_default="user"))


def downgrade() -> None:
    op.drop_column("users", "role")
