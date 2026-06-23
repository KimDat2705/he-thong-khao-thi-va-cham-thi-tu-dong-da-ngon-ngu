"""add score_listening and score_reading to grades (SPEC-GRADE-002)

Revision ID: a1b2c3d4e5f6
Revises: 69936c2cdac2
Create Date: 2026-06-23 09:00:00.000000

Adds semantically-named columns for objective L&R scaled scores so the TOEIC
grader no longer borrows score_speaking/score_writing (which remain for the
essay/AI grading path). Additive only — no data loss.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '69936c2cdac2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('grades', sa.Column('score_listening', sa.Float(), nullable=True))
    op.add_column('grades', sa.Column('score_reading', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('grades', 'score_reading')
    op.drop_column('grades', 'score_listening')
