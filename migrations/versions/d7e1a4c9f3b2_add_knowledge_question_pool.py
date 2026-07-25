"""add_knowledge_question_pool

Revision ID: d7e1a4c9f3b2
Revises: c4a8f2e6b1d9
Create Date: 2026-07-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7e1a4c9f3b2'
down_revision = 'c4a8f2e6b1d9'
branch_labels = None
depends_on = None


def upgrade():
    # JSON-encoded list of KnowledgeQuestion ids assigned to this team for this booth, chosen
    # once from that booth's full question bank. Nullable, no backfill -- see
    # TeamMission.knowledge_question_pool in app/models.py.
    op.add_column('team_missions', sa.Column('knowledge_question_pool', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('team_missions', 'knowledge_question_pool')
