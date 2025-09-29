"""add or update invoice_receipts table"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic
revision = "add_invoice_receipts_table"
down_revision = "c4b27d75b018"  # твоя предыдущая миграция
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "invoice_receipts" not in insp.get_table_names():
        # Таблицы нет → создаём целиком
        op.create_table(
            "invoice_receipts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False, index=True),
            sa.Column("file_path", sa.String, nullable=False),
            sa.Column("uploaded_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), index=True),
            sa.Column("expired_at", sa.DateTime, nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending", index=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        )

        op.create_index(
            "ix_invoice_receipts_invoice_status",
            "invoice_receipts",
            ["invoice_id", "status"],
            unique=False
        )
    else:
        # Таблица есть → проверяем недостающие колонки
        cols = [c["name"] for c in insp.get_columns("invoice_receipts")]

        with op.batch_alter_table("invoice_receipts") as batch:
            if "status" not in cols:
                batch.add_column(sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"))
            if "amount" not in cols:
                batch.add_column(sa.Column("amount", sa.Numeric(12, 2), nullable=True))

        # Индекс
        indexes = [i["name"] for i in insp.get_indexes("invoice_receipts")]
        if "ix_invoice_receipts_invoice_status" not in indexes:
            op.create_index(
                "ix_invoice_receipts_invoice_status",
                "invoice_receipts",
                ["invoice_id", "status"],
                unique=False
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "invoice_receipts" in insp.get_table_names():
        with op.batch_alter_table("invoice_receipts") as batch:
            if "amount" in [c["name"] for c in insp.get_columns("invoice_receipts")]:
                batch.drop_column("amount")
            if "status" in [c["name"] for c in insp.get_columns("invoice_receipts")]:
                batch.drop_column("status")

        indexes = [i["name"] for i in insp.get_indexes("invoice_receipts")]
        if "ix_invoice_receipts_invoice_status" in indexes:
            op.drop_index("ix_invoice_receipts_invoice_status", table_name="invoice_receipts")
