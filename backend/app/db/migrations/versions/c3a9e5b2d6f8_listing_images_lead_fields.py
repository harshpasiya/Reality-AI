"""listing images and lead message / status / conversation

Schema recommendations R6 (photos, JSON column) and R7 (lead message,
status, conversation link, one lead per customer and listing).

Revision ID: c3a9e5b2d6f8
Revises: b2e7d3a8c1f4
Create Date: 2026-10-26 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a9e5b2d6f8'
down_revision: Union[str, None] = 'b2e7d3a8c1f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listing', sa.Column('images', sa.JSON(), nullable=True))

    op.add_column('lead', sa.Column('message', sa.Text(), nullable=True))
    op.add_column(
        'lead',
        sa.Column('status', sa.String(length=20), server_default='new', nullable=False),
    )
    op.add_column('lead', sa.Column('conversation_id', sa.Integer(), nullable=True))
    op.add_column(
        'lead',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_foreign_key(
        'fk_lead_conversation_id', 'lead', 'conversation', ['conversation_id'], ['id']
    )
    op.create_index('ix_lead_conversation_id', 'lead', ['conversation_id'])
    op.create_check_constraint(
        'ck_lead_status',
        'lead',
        "status IN ('new', 'contacted', 'visit_scheduled', 'closed', 'lost')",
    )

    # The old /chat code could create one lead per search result; keep the
    # earliest lead per (listing, customer) before enforcing uniqueness.
    op.execute(
        "DELETE FROM lead a USING lead b "
        "WHERE a.listing_id = b.listing_id AND a.customer_id = b.customer_id "
        "AND a.id > b.id"
    )
    op.create_unique_constraint(
        'uq_lead_listing_customer', 'lead', ['listing_id', 'customer_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_lead_listing_customer', 'lead', type_='unique')
    op.drop_constraint('ck_lead_status', 'lead', type_='check')
    op.drop_index('ix_lead_conversation_id', table_name='lead')
    op.drop_constraint('fk_lead_conversation_id', 'lead', type_='foreignkey')
    op.drop_column('lead', 'updated_at')
    op.drop_column('lead', 'conversation_id')
    op.drop_column('lead', 'status')
    op.drop_column('lead', 'message')
    op.drop_column('listing', 'images')
