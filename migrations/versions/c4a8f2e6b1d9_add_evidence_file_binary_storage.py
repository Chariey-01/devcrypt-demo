"""add_evidence_file_binary_storage

Revision ID: c4a8f2e6b1d9
Revises: b3f7d1e8c5a4
Create Date: 2026-07-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4a8f2e6b1d9'
down_revision = 'b3f7d1e8c5a4'
branch_labels = None
depends_on = None


def upgrade():
    # Real uploaded evidence files (image/PDF), stored as bytes in the DB rather than local
    # disk -- Railway has no persistent filesystem guarantee. All three nullable, no backfill --
    # existing text-mode EvidenceFile rows just leave them NULL. See EvidenceFile in
    # app/models.py.
    op.add_column('evidence_files', sa.Column('data', sa.LargeBinary(), nullable=True))
    op.add_column('evidence_files', sa.Column('mime_type', sa.String(length=100), nullable=True))
    op.add_column('evidence_files', sa.Column('filename', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('evidence_files', 'filename')
    op.drop_column('evidence_files', 'mime_type')
    op.drop_column('evidence_files', 'data')
