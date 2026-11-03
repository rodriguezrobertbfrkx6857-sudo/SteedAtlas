"""Initial migration: create all tables

Revision ID: 8b923d6c8edc
Revises: 
Create Date: 2026-04-19 10:31:19.655738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b923d6c8edc'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('nickname', sa.String(length=100), nullable=False),
        sa.Column('avatar', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('wechat_openid', sa.String(length=100), nullable=True),
        sa.Column('hashed_password', sa.String(length=200), nullable=True),
        sa.Column('tier', sa.String(length=20), nullable=True),
        sa.Column('purchase_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('wechat_openid')
    )
    
    # Create horses table
    op.create_table(
        'horses',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('rarity', sa.String(length=10), nullable=False),
        sa.Column('image', sa.String(length=500), nullable=False),
        sa.Column('story', sa.Text(), nullable=False),
        sa.Column('full_story', sa.Text(), nullable=True),
        sa.Column('historical_source', sa.String(length=200), nullable=True),
        sa.Column('dynasty', sa.String(length=50), nullable=True),
        sa.Column('owner', sa.String(length=100), nullable=True),
        sa.Column('trait', sa.String(length=100), nullable=False),
        sa.Column('traits', sa.JSON(), nullable=True),
        sa.Column('drop_rate', sa.Float(), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create products table
    op.create_table(
        'products',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('horse_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('stock', sa.Integer(), nullable=True),
        sa.Column('images', sa.JSON(), nullable=True),
        sa.Column('specs', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['horse_id'], ['horses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('items', sa.JSON(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('shipping_address', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create gacha_records table
    op.create_table(
        'gacha_records',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('horse_id', sa.String(length=50), nullable=False),
        sa.Column('rarity', sa.String(length=10), nullable=False),
        sa.Column('draw_type', sa.String(length=20), nullable=False),
        sa.Column('pity_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['horse_id'], ['horses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create collections table
    op.create_table(
        'collections',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('horse_id', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('obtained_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['horse_id'], ['horses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('collections')
    op.drop_table('gacha_records')
    op.drop_table('orders')
    op.drop_table('products')
    op.drop_table('horses')
    op.drop_table('users')
