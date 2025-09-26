from decimal import Decimal
from sqlalchemy.orm import configure_mappers
from sqlalchemy import text

from app.db import Base, engine, SessionLocal
import app.models  # подтягиваем все модели

from app.models.catalog import Seller, Category, Product, Variant
from app.models.user import User
from app.utils.security import hash_password
from app.utils.enums import UserRole
from app.models.subscriber import Subscriber


def run_seed():
    # === RESET ===
    Base.metadata.drop_all(bind=engine)
    print("🗑 Все таблицы удалены")

    configure_mappers()
    Base.metadata.create_all(bind=engine)
    print("✅ Все таблицы пересозданы")

    db = SessionLocal()
    try:
        # --- Продавец ---
        seller = Seller(name="Магазин №1", city="Алматы")
        db.add(seller)
        db.commit()
        db.refresh(seller)
        print(f"✅ Продавец создан: {seller.name}")

        # --- Категория ---
        category = Category(name="Посуда", slug="posuda")
        db.add(category)
        db.commit()
        db.refresh(category)
        print(f"✅ Категория создана: {category.name}")

        # --- Пользователи ---
        users = [
            ("admin", "123456", UserRole.ADMIN.value),
            ("seller", "123456", UserRole.SELLER.value),
            ("picker", "123456", UserRole.PICKER.value),
        ]

        for username, raw_password, role in users:
            exists = db.execute(
                text("SELECT id FROM users WHERE username = :u"),
                {"u": username}
            ).fetchone()

            if not exists:
                password_hashed = hash_password(raw_password)
                db.execute(
                    text("INSERT INTO users (username, password_hash, role) VALUES (:u, :p, :r)"),
                    {"u": username, "p": password_hashed, "r": role}
                )
                db.commit()
                print(f"✅ User created (username='{username}', password='{raw_password}', role='{role}')")
            else:
                print(f"ℹ️ User '{username}' already exists")
        channel_chat_id = "-1002878414324"
        subscriber = Subscriber(chat_id=channel_chat_id, username="shop_channel")
        db.add(subscriber)
        db.commit()
        print(f"✅ Канал добавлен как подписчик: {channel_chat_id}")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
