"""invoice receipts + is_paid"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "c4b27d75b018"
down_revision = "c9cf57f21df7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем колонку is_paid с дефолтом false
    op.add_column(
        "invoices",
        sa.Column(
            "is_paid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false")
        )
    )

    # Если нужно убрать server_default после проставления значений:
    op.alter_column("invoices", "is_paid", server_default=None)


def downgrade() -> None:
    op.drop_column("invoices", "is_paid")
