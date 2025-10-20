"""add salespersons table and link invoices

Revision ID: 442ce8681842
Revises: d4dc3bb7de1e
Create Date: 2025-10-20 17:42:57.555915
"""
from typing import Sequence, Union
from datetime import datetime
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "442ce8681842"
down_revision: Union[str, Sequence[str], None] = "d4dc3bb7de1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1️⃣ Создаём таблицу salespersons
    op.create_table(
        "salespersons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "seller_id",
            sa.Integer(),
            sa.ForeignKey("sellers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 2️⃣ Добавляем колонку salesperson_id в invoices
    op.add_column(
        "invoices",
        sa.Column(
            "salesperson_id",
            sa.Integer(),
            sa.ForeignKey("salespersons.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3️⃣ Для каждого магазина создаём дефолтного продавца
    connection = op.get_bind()

    sellers = connection.execute(sa.text("SELECT id FROM sellers")).fetchall()
    for seller in sellers:
        seller_id = seller[0]

        # создаём дефолтного продавца для магазина
        connection.execute(
            sa.text(
                """
                INSERT INTO salespersons (seller_id, name, phone, created_at)
                VALUES (:seller_id, :name, NULL, NOW())
                """
            ),
            {"seller_id": seller_id, "name": "Default Seller"},
        )

        # получаем id нового продавца
        salesperson_id = connection.execute(
            sa.text(
                """
                SELECT id FROM salespersons
                WHERE seller_id = :seller_id
                ORDER BY id DESC LIMIT 1
                """
            ),
            {"seller_id": seller_id},
        ).scalar()

        # 4️⃣ Всем накладным, у которых есть хотя бы один товар этого магазина,
        #     проставляем salesperson_id
        connection.execute(
            sa.text(
                """
                UPDATE invoices
                SET salesperson_id = :spid
                WHERE id IN (
                    SELECT DISTINCT invoice_id
                    FROM invoice_items
                    WHERE seller_id = :sid
                )
                """
            ),
            {"spid": salesperson_id, "sid": seller_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("invoices", "salesperson_id")
    op.drop_table("salespersons")
