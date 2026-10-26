"""listing status, updated_at, view_count and rooms.bedrooms rule

Schema recommendations R1 (rooms bedrooms key), R2 (status), R3 (updated_at)
plus a view counter for broker analytics.

Revision ID: a1f4c2d9b7e0
Revises: e3eba316c2f3
Create Date: 2026-10-26 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f4c2d9b7e0'
down_revision: Union[str, None] = 'e3eba316c2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'listing',
        sa.Column('status', sa.String(length=20), server_default='available', nullable=False),
    )
    op.create_check_constraint(
        'ck_listing_status',
        'listing',
        "status IN ('available', 'under_offer', 'sold', 'withdrawn')",
    )
    op.create_index('ix_listing_status', 'listing', ['status'])

    op.add_column(
        'listing',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.add_column(
        'listing',
        sa.Column('view_count', sa.Integer(), server_default='0', nullable=False),
    )

    # rooms.bedrooms must be a whole number when present, so the AI's
    # (rooms->>'bedrooms')::int filter and the index below can never fail.
    op.create_check_constraint(
        'ck_listing_rooms_bedrooms',
        'listing',
        "rooms IS NULL OR rooms::jsonb->'bedrooms' IS NULL "
        "OR (rooms::jsonb->>'bedrooms') ~ '^[0-9]+$'",
    )
    op.execute(
        "CREATE INDEX ix_listing_bedrooms ON listing (((rooms->>'bedrooms')::int))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_listing_bedrooms")
    op.drop_constraint('ck_listing_rooms_bedrooms', 'listing', type_='check')
    op.drop_column('listing', 'view_count')
    op.drop_column('listing', 'updated_at')
    op.drop_index('ix_listing_status', table_name='listing')
    op.drop_constraint('ck_listing_status', 'listing', type_='check')
    op.drop_column('listing', 'status')
