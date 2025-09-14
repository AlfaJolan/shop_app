# app/models/order_status_log.py
from typing import Optional
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class OrderStatusLog(Base):
    __tablename__ = "order_status_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)

    old_status: Mapped[str] = mapped_column(String(24))
    new_status: Mapped[str] = mapped_column(String(24))
    user: Mapped[str] = mapped_column(String(64), default="admin")  # позже прикрутим реальных пользователей
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order = relationship("Order")
