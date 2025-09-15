# scripts/reset_and_seed.py
from app.db import Base, engine, SessionLocal
import app.models  # важно: подтягиваем все модели
from sqlalchemy.orm import configure_mappers


def reset_and_seed():
    # === RESET ===
    Base.metadata.drop_all(bind=engine)
    print("🗑 Все таблицы удалены")

    configure_mappers()
    Base.metadata.create_all(bind=engine)
    print("✅ Все таблицы пересозданы")

    # === SEED ===
    from app.models.catalog import Seller, Category, Product, Variant

    db = SessionLocal()
    try:
        # --- 1. Продавец ---
        seller = Seller(name="Магазин №1", city="Алматы")
        db.add(seller)
        db.commit()
        db.refresh(seller)
        print(f"✅ Продавец создан: {seller.name}")

        # --- 2. Категория ---
        category = Category(name="Продукты", slug="produkty")
        db.add(category)
        db.commit()
        db.refresh(category)
        print(f"✅ Категория создана: {category.name}")

        # --- 3. Товары ---
        milk = Product(
            name="Молоко",
            sku="MILK001",
            unit="литр",
            image="milk.png",
            is_active=True,
            category_id=category.id,
            seller_id=seller.id,
        )
        sugar = Product(
            name="Сахар",
            sku="SUGAR001",
            unit="кг",
            image="sugar.png",
            is_active=True,
            category_id=category.id,
            seller_id=seller.id,
        )
        db.add_all([milk, sugar])
        db.commit()
        db.refresh(milk)
        db.refresh(sugar)
        print(f"✅ Товар создан: {milk.name}")
        print(f"✅ Товар создан: {sugar.name}")

        # --- 4. Варианты ---
        milk_var = Variant(
            product_id=milk.id,
            name="Обычное молоко",
            pack_size=1,
            unit_price=250,
            stock=10,
            is_active=True,
        )
        sugar_var = Variant(
            product_id=sugar.id,
            name="Сахар-песок",
            pack_size=1,
            unit_price=300,
            stock=20,
            is_active=True,
        )
        db.add_all([milk_var, sugar_var])
        db.commit()
        print("✅ Варианты добавлены")

    finally:
        db.close()


if __name__ == "__main__":
    reset_and_seed()
