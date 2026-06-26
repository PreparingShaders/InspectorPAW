"""add is_done to workout_sets

Revision ID: 087df340dd57
Revises: 087df340dd56

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '087df340dd57'
down_revision: Union[str, None] = '087df340dd56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workout_sets', sa.Column('is_done', sa.Boolean(), server_default='0'))


def downgrade() -> None:
    op.drop_column('workout_sets', 'is_done')