"""change_default_exam_type_to_vstep_b1

Revision ID: 80e0b6818813
Revises: 1d0c144e22d2
Create Date: 2026-06-30 11:20:23.819874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
"""change_default_exam_type_to_vstep_b1

Revision ID: 80e0b6818813
Revises: 1d0c144e22d2
Create Date: 2026-06-30 11:20:23.819874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80e0b6818813'
down_revision: Union[str, Sequence[str], None] = '1d0c144e22d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Alter the server default of exam_type to VSTEP_B1
    op.alter_column('questions', 'exam_type', server_default='VSTEP_B1')


def downgrade() -> None:
    """Downgrade schema."""
    # Restore the server default of exam_type to TOEIC
    op.alter_column('questions', 'exam_type', server_default='TOEIC')
