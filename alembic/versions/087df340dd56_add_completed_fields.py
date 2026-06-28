"""add is_completed and completed_at to workout_sessions

Revision ID: 087df340dd56
Revises: 087df340dd55

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '087df340dd56'
down_revision: Union[str, None] = '087df340dd55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workout_sessions', sa.Column('is_completed', sa.Boolean(), server_default='0'))
    op.add_column('workout_sessions', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('workout_sessions', 'completed_at')
    op.drop_column('workout_sessions', 'is_completed')