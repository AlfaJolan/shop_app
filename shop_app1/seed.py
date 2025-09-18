# scripts/reset_and_seed_basic.py
from app.db import Base, engine, SessionLocal
from sqlalchemy.orm import configure_mappers
from decimal import Decimal
import app.models  # подтягиваем все модели
from app.models.catalog import Seller, Category, Product, Variant
from app.utils.security import hash_password
from app.models import Base
from sqlalchemy import text

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

        # --- 21 Товар ---
        for i in range(1, 22):  # 1..21
            product = Product(
                name=str(i),
                sku=f"SKU{i:03d}",
                unit="шт",
                image=f"{i}.jpg",
                is_active=True,
                category_id=category.id,
                seller_id=seller.id,
            )
            db.add(product)
            db.flush()

            variant = Variant(
                product_id=product.id,
                name="Основной вариант",
                pack_size=1,
                unit_price=Decimal(i),  # цена = имя
                stock=20,
                is_active=True,
            )
            db.add(variant)

            db.commit()
            print(f"✅ Товар создан: {product.name}")

        # --- Admin User ---
        # напрямую SQL, т.к. у тебя users не в ORM
        password_hash = hash_password("Bl00dType")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                role TEXT
            )
        """))
        db.commit()

        exists = db.execute(text("SELECT id FROM users WHERE username = 'admin'")).fetchone()
        if not exists:
            db.execute(text(
                "INSERT INTO users (username, password_hash, is_admin, role) VALUES (:u, :p, 1, 'admin')"
            ), {"u": "admin", "p": password_hash})
            db.commit()
            print("✅ Admin user created (username='admin', password='123456')")
        else:
            print("ℹ️ Admin user already exists")

        print("🎉 Готово: БД заполнена тестовыми данными!")

    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
