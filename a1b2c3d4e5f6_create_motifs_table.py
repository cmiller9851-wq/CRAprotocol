"""create motifs table

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2026-01-23 13:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # [span_4](start_span)Implementation of Database Schema[span_4](end_span)
    op.create_table(
        'motifs',
        sa.Column('id', sa.Integer(), sa.Sequence('motifs_id_seq'), primary_key=True),
        sa.Column('motif_text', sa.Text(), nullable=False),
        sa.Column('canonized_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('anchor_txid', sa.Text(), nullable=True),
        sa.Column('integrity_hash', sa.String(length=64), nullable=True) # CRA standard enhancement
    )
    
    # [span_5](start_span)Implementation of required Index[span_5](end_span)
    op.create_index('idx_motif_anchor', 'motifs', ['anchor_txid'], unique=False)

def downgrade():
    op.drop_index('idx_motif_anchor', table_name='motifs')
    op.drop_table('motifs')
