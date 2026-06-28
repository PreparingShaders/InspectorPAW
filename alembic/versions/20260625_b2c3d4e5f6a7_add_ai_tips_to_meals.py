"""add_ai_tips_to_meals

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-25 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('meals', sa.Column('protein_ai_tip', sa.String(), nullable=True))
    op.add_column('meals', sa.Column('fat_ai_tip', sa.String(), nullable=True))
    op.add_column('meals', sa.Column('carb_ai_tip', sa.String(), nullable=True))
    op.add_column('meals', sa.Column('processing_ai_tip', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('meals', 'processing_ai_tip')
    op.drop_column('meals', 'carb_ai_tip')
    op.drop_column('meals', 'fat_ai_tip')
    op.drop_column('meals', 'protein_ai_tip')
