"""Add Shopee publish option catalogs

Revision ID: 1f4a2d7c9b31
Revises: b6f2c9d4e811
Create Date: 2026-04-20 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f4a2d7c9b31"
down_revision: Union[str, None] = "b6f2c9d4e811"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shopee_publish_configs") as batch_op:
        batch_op.add_column(sa.Column("category_options_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("logistic_options_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("shopee_publish_configs") as batch_op:
        batch_op.drop_column("logistic_options_json")
        batch_op.drop_column("category_options_json")
