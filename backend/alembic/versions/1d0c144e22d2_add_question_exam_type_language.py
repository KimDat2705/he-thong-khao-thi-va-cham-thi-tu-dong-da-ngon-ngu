"""add_question_exam_type_language

Revision ID: 1d0c144e22d2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-25 10:09:53.050440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d0c144e22d2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('questions', sa.Column('exam_type', sa.String(), server_default='TOEIC', nullable=False))
    op.add_column('questions', sa.Column('language', sa.String(), server_default='EN', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('questions', 'language')
    op.drop_column('questions', 'exam_type')
