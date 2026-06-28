"""add workout tables

Revision ID: 087df340dd54
Revises: b2c3d4e5f6a7
Create Date: 2026-06-26 22:18:58.592134

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '087df340dd54'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exercise_library',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('muscle_group', sa.String(), nullable=True),
        sa.Column('equipment', sa.String(), nullable=True),
    )

    op.create_table(
        'workout_sessions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('duration_min', sa.Integer(), nullable=True),
        sa.Column('feeling', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    op.create_table(
        'workout_exercises',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('workout_sessions.id'), nullable=False),
        sa.Column('exercise_id', sa.Integer(), sa.ForeignKey('exercise_library.id'), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )

    op.create_table(
        'workout_sets',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('exercise_entry_id', sa.Integer(), sa.ForeignKey('workout_exercises.id'), nullable=False),
        sa.Column('set_number', sa.Integer(), nullable=False),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('reps', sa.Integer(), nullable=True),
        sa.Column('rpe', sa.Float(), nullable=True),
        sa.Column('is_warmup', sa.Boolean(), server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('workout_sets')
    op.drop_table('workout_exercises')
    op.drop_table('workout_sessions')
    op.drop_table('exercise_library')
