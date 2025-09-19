from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer
from app.db import Base
from app.utils.enums import UserRole  # 👈 импорт enum ролей


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 🔹 роль пользователя
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=UserRole.SELLER.value  # по умолчанию — продавец
    )
