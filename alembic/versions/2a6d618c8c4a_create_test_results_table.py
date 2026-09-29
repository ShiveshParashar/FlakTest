"""create test results table

Revision ID: 2a6d618c8c4a
Revises: 71e858e484a7
Create Date: 2026-09-29 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a6d618c8c4a'
down_revision: Union[str, Sequence[str], None] = '71e858e484a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('test_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('test_run_id', sa.Integer(), nullable=False),
    sa.Column('test_name', sa.String(length=500), nullable=False),
    sa.Column('outcome', sa.String(length=50), nullable=False),
    sa.Column('duration', sa.Float(), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['test_run_id'], ['test_runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_results_id'), 'test_results', ['id'], unique=False)
    op.create_index(op.f('ix_test_results_test_run_id'), 'test_results', ['test_run_id'], unique=False)
    op.create_index(op.f('ix_test_results_test_name'), 'test_results', ['test_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_test_results_test_name'), table_name='test_results')
    op.drop_index(op.f('ix_test_results_test_run_id'), table_name='test_results')
    op.drop_index(op.f('ix_test_results_id'), table_name='test_results')
    op.drop_table('test_results')
