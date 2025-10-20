"""add chat_type to subscribers

Revision ID: d4dc3bb7de1e
Revises: add_invoice_receipts_table
Create Date: 2025-10-19 21:18:02.269972
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4dc3bb7de1e'
down_revision: Union[str, Sequence[str], None] = 'add_invoice_receipts_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # === обновления от автогенерации ===
    #op.drop_index(op.f('ix_invoice_receipts_invoice_status'), table_name='invoice_receipts')
    op.create_index(op.f('ix_invoice_receipts_status'), 'invoice_receipts', ['status'], unique=False)
    op.create_index(op.f('ix_invoices_is_paid'), 'invoices', ['is_paid'], unique=False)

    # === исправленный блок добавления chat_type ===
    # 1️⃣ Добавляем колонку nullable=True, чтобы не упала миграция
    op.add_column(
        'subscribers',
        sa.Column('chat_type', sa.String(length=32), nullable=True)
    )

    # 2️⃣ Проставляем значение по умолчанию для существующих строк
    op.execute("UPDATE subscribers SET chat_type = 'sales' WHERE chat_type IS NULL;")

    # 3️⃣ Делаем колонку NOT NULL и создаём индекс
    op.alter_column('subscribers', 'chat_type', nullable=False)
    op.create_index(op.f('ix_subscribers_chat_type'), 'subscribers', ['chat_type'], unique=False)

    # 4️⃣ Остальные изменения (из автогенерации)
    op.alter_column(
        'subscribers', 'added_at',
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
        existing_server_default=sa.text('now()')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_subscribers_chat_type'), table_name='subscribers')
    op.alter_column(
        'subscribers', 'added_at',
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=True,
        existing_server_default=sa.text('now()')
    )
    op.drop_column('subscribers', 'chat_type')
    op.drop_index(op.f('ix_invoices_is_paid'), table_name='invoices')
    op.drop_index(op.f('ix_invoice_receipts_status'), table_name='invoice_receipts')
    op.create_index(
        op.f('ix_invoice_receipts_invoice_status'),
        'invoice_receipts',
        ['invoice_id', 'status'],
        unique=False
    )
