"""add is_template and template_id to workout_sessions

Revision ID: 087df340dd55
Revises: 087df340dd54

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '087df340dd55'
down_revision: Union[str, None] = '087df340dd54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workout_sessions', sa.Column('is_template', sa.Boolean(), server_default='0'))
    op.add_column('workout_sessions', sa.Column('template_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('workout_sessions', 'template_id')
    op.drop_column('workout_sessions', 'is_template')