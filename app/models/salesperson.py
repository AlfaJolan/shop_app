# app/models/salesperson.py
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey

from app.db import Base


class Salesperson(Base):
    __tablename__ = "salespersons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # связи
    seller: Mapped["Seller"] = relationship(back_populates="salespersons")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="salesperson")
