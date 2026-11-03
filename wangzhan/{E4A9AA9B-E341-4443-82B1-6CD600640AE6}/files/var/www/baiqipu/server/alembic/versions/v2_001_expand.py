"""Expand-only V2 entities, revisions, jobs, leased nodes and audit outbox."""
from alembic import op
from app.v2.models import Entity, Revision, Job, Node, Event

revision = 'v2_001'
down_revision = 'a8d4e7f9c201'
branch_labels = None
depends_on = None


def upgrade():
    for model in (Entity, Revision, Job, Node, Event):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    # V2-only tables; export V2 data first. Legacy rows/tables are not touched.
    for model in (Event, Node, Job, Revision, Entity):
        model.__table__.drop(op.get_bind(), checkfirst=True)
