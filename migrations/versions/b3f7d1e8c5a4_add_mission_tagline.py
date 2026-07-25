"""add_mission_tagline

Revision ID: b3f7d1e8c5a4
Revises: a9c2e6f1b4d8
Create Date: 2026-07-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3f7d1e8c5a4'
down_revision = 'a9c2e6f1b4d8'
branch_labels = None
depends_on = None


def upgrade():
    # Short employer-facing line shown on the cipher card and booth panel, distinct from the
    # full narrative paragraph. Nullable, no backfill -- see Mission.tagline in app/models.py.
    op.add_column('missions', sa.Column('tagline', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('missions', 'tagline')
