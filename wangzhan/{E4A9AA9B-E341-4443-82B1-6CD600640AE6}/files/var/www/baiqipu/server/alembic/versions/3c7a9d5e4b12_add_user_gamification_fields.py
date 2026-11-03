"""Add user gamification fields

Revision ID: 3c7a9d5e4b12
Revises: 1f4a2d7c9b31
Create Date: 2026-04-20 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c7a9d5e4b12"
down_revision: Union[str, None] = "1f4a2d7c9b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("checkin_streak", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("total_checkins", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("last_checkin_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_checkin_date")
        batch_op.drop_column("total_checkins")
        batch_op.drop_column("checkin_streak")
