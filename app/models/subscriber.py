# app/models/subscriber.py
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Subscriber(Base):
    """
    Таблица подписчиков Telegram-бота.

    Используется для рассылки уведомлений (продажи, аналитика, админ-уведомления).
    """
    __tablename__ = "subscribers"

    # 🔹 Уникальный идентификатор
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 🔹 ID чата в Telegram (строка, т.к. бывают большие числа)
    chat_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # 🔹 Username пользователя (@username)
    username: Mapped[str] = mapped_column(String(120), nullable=True)

    # 🔹 Когда добавлен
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 🔹 Тип чата: "sales", "analytics", "admin"
    chat_type: Mapped[str] = mapped_column(String(32), default="sales", index=True)
