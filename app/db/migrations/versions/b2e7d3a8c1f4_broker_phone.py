"""broker phone (displayable, E.164)

Schema recommendation R5, option A: a readable phone shown only to the
broker and to customers who have created a lead.  phone_hash is kept.

Revision ID: b2e7d3a8c1f4
Revises: a1f4c2d9b7e0
Create Date: 2026-10-26 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e7d3a8c1f4'
down_revision: Union[str, None] = 'a1f4c2d9b7e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('broker', sa.Column('phone', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('broker', 'phone')
