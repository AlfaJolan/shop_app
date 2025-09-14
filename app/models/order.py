# app/models/order.py
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    customer_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # === СТАТУС ЗАКАЗА ===
    # допустимые значения: 'new' | 'packed' | 'shipped' | 'delivered' | 'cancelled'
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)

    product_id: Mapped[int] = mapped_column(Integer)
    variant_id: Mapped[int] = mapped_column(Integer)

    product_name: Mapped[str] = mapped_column(String(255))
    variant_name: Mapped[str] = mapped_column(String(120))

    qty: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped["Order"] = relationship("Order", back_populates="items")
