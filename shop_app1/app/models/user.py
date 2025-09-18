from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 🔹 поле для роли
