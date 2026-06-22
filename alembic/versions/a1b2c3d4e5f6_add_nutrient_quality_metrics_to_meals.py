"""add_nutrient_quality_metrics_to_meals

Revision ID: a1b2c3d4e5f6
Revises: 2c9629bb56e3
Create Date: 2026-06-22 17:06:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '051159291039'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('meals', 'processing_level')
    op.drop_column('meals', 'satiety_index')
    op.drop_column('meals', 'micronutrient_density')

    op.add_column('meals', sa.Column('amino_acid_score', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('animal_protein_ratio', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('protein_density', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('omega6_omega3_ratio', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('trans_fat_ratio', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('saturated_fat_ratio', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('monounsaturated_fat_ratio', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('polyunsaturated_fat_ratio', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('glycemic_load', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('fiber_to_carb_ratio', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('added_sugar_ratio', sa.Float(), nullable=True))
    op.add_column('meals', sa.Column('nova_processing_level', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('meals', 'nova_processing_level')
    op.drop_column('meals', 'added_sugar_ratio')
    op.drop_column('meals', 'fiber_to_carb_ratio')
    op.drop_column('meals', 'glycemic_load')
    op.drop_column('meals', 'polyunsaturated_fat_ratio')
    op.drop_column('meals', 'monounsaturated_fat_ratio')
    op.drop_column('meals', 'saturated_fat_ratio')
    op.drop_column('meals', 'trans_fat_ratio')
    op.drop_column('meals', 'omega6_omega3_ratio')
    op.drop_column('meals', 'protein_density')
    op.drop_column('meals', 'animal_protein_ratio')
    op.drop_column('meals', 'amino_acid_score')

    op.add_column('meals', sa.Column('micronutrient_density', sa.Enum('HIGH', 'MEDIUM', 'LOW', name='micronutrientdensity'), nullable=True))
    op.add_column('meals', sa.Column('satiety_index', sa.Integer(), nullable=True))
    op.add_column('meals', sa.Column('processing_level', sa.Enum('WHOLE', 'MINIMALLY_PROCESSED', 'ULTRA_PROCESSED', name='processinglevel'), nullable=True))
