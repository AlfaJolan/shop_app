from decimal import Decimal
from sqlalchemy.orm import configure_mappers
from sqlalchemy import text

from app.db import Base, engine, SessionLocal
import app.models  # подтягиваем все модели

from app.models.catalog import Seller, Category, Product, Variant
from app.utils.security import hash_password
from app.utils.enums import UserRole
from app.models.subscriber import Subscriber


def run_seed():
    print("🚀 Старт seed...")

    print("1) Удаляем таблицы...")
    Base.metadata.drop_all(bind=engine)
    print("✅ Все таблицы удалены")

    print("2) Конфигурируем мапперы...")
    configure_mappers()
    print("✅ Мапперы готовы")

    print("3) Создаем таблицы...")
    Base.metadata.create_all(bind=engine)
    print("✅ Все таблицы пересозданы")

    db = SessionLocal()

    try:
        print("4) Создаем продавца...")
        seller = Seller(name="Магазин №1", city="Алматы")
        db.add(seller)
        db.flush()
        print(f"✅ Продавец подготовлен: {seller.name}")

        print("5) Создаем категорию...")
        category = Category(name="Посуда", slug="posuda")
        db.add(category)
        db.flush()
        print(f"✅ Категория подготовлена: {category.name}")

        print("6) Создаем товары и варианты...")
        products_data = [
            {
                "name": "Тарелка глубокая",
                "sku": "SKU1001",
                "variant_name": "Белая 24 см",
                "cost": Decimal("500"),
                "price": Decimal("850"),
                "stock": 40,
            },
            {
                "name": "Кружка керамическая",
                "sku": "SKU1002",
                "variant_name": "350 мл",
                "cost": Decimal("350"),
                "price": Decimal("700"),
                "stock": 60,
            },
            {
                "name": "Сковорода",
                "sku": "SKU1003",
                "variant_name": "28 см",
                "cost": Decimal("2500"),
                "price": Decimal("3900"),
                "stock": 15,
            },
        ]

        for item in products_data:
            product = Product(
                name=item["name"],
                sku=item["sku"],
                unit="шт",
                image=None,
                is_active=True,
                category_id=category.id,
                seller_id=seller.id,
            )
            db.add(product)
            db.flush()

            variant = Variant(
                product_id=product.id,
                name=item["variant_name"],
                pack_size=1,
                unit_price=item["price"],
                unit_price_net_cost=item["cost"],
                stock=item["stock"],
                is_active=True,
            )
            db.add(variant)

            print(f"✅ Подготовлен товар: {product.name}")

        print("7) Создаем пользователей...")
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
                    text(
                        "INSERT INTO users (username, password_hash, role) "
                        "VALUES (:u, :p, :r)"
                    ),
                    {"u": username, "p": password_hashed, "r": role}
                )
                print(f"✅ Подготовлен user: {username}")
            else:
                print(f"ℹ️ User '{username}' уже существует")

        print("8) Создаем подписчиков...")
        subscribers = [
            Subscriber(
                chat_id="-1002878414324",
                username="shop_channel",
                chat_type="sales",
            ),
            Subscriber(
                chat_id="-1002932041028",
                username="shop_channel",
                chat_type="analytics",
            ),
        ]

        db.add_all(subscribers)
        print("✅ Подписчики подготовлены")

        print("9) Финальный commit...")
        db.commit()
        print("🎉 Seed успешно завершен")

    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка во время seed: {e}")
        raise
    finally:
        db.close()
        print("🔒 Сессия закрыта")


if __name__ == "__main__":
    run_seed()