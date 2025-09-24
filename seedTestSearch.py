import random
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

        # --- Категории и товары ---
        categories_with_products = {
            "Сыромолочные": [
                "Сыр Пармезан", "Сыр Чеддер", "Сыр Моцарелла", "Сметана", "Кефир",
                "Молоко", "Йогурт натуральный", "Сливки", "Масло сливочное", "Сыр Голландский",
                "Творог", "Брынза", "Сыр Рокфор", "Сыр Адыгейский", "Айран"
            ],
            "Мясо": [
                "Колбаса куриная", "Колбаса говяжья", "Бекон", "Фарш говяжий", "Фарш куриный",
                "Куриное филе", "Говядина стейк", "Свинина на кости", "Шашлык свиной", "Рёбра говяжьи",
                "Пельмени", "Сосиски молочные", "Гуляш говяжий", "Филе индейки", "Куриные крылья"
            ],
            "Овощи и фрукты": [
                "Яблоки", "Апельсины", "Бананы", "Виноград", "Мандарины",
                "Картофель", "Морковь", "Лук репчатый", "Огурцы свежие", "Помидоры",
                "Капуста", "Чеснок", "Свекла", "Перец болгарский", "Клубника"
            ],
            "Напитки": [
                "Минеральная вода", "Газированная вода", "Сок апельсиновый", "Сок яблочный", "Сок мультифрукт",
                "Кола", "Фанта", "Спрайт", "Чай черный", "Чай зеленый",
                "Кофе растворимый", "Кофе зерновой", "Энергетик", "Квас", "Молочный коктейль"
            ],
            "Бытовые товары": [
                "Зажигалка", "Спички", "Мыло хозяйственное", "Мыло туалетное", "Шампунь",
                "Гель для душа", "Зубная паста", "Зубная щетка", "Стиральный порошок", "Кондиционер для белья",
                "Средство для посуды", "Губки кухонные", "Пакеты для мусора", "Туалетная бумага", "Полотенца бумажные"
            ],
        }

        for cat_name, products in categories_with_products.items():
            category = Category(name=cat_name, slug=cat_name.lower().replace(" ", "_"))
            db.add(category)
            db.commit()
            db.refresh(category)
            print(f"✅ Категория создана: {category.name}")

            for pname in products:
                product = Product(
                    name=pname,
                    sku=f"SKU{random.randint(1000,9999)}",
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
                    name="Основной вариант",
                    pack_size=1,
                    unit_price=Decimal(random.randint(10, 1000)),
                    unit_price_net_cost=Decimal(random.randint(10, 900)),
                    stock=random.randint(10, 100),
                    is_active=True,
                )
                db.add(variant)
                db.commit()
                print(f"✅ Товар создан: {product.name}")

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

        # --- Канал-подписчик ---
        channel_chat_id = "-1002878414324"
        subscriber = Subscriber(chat_id=channel_chat_id, username="shop_channel")
        db.add(subscriber)
        db.commit()
        print(f"✅ Канал добавлен как подписчик: {channel_chat_id}")

    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
