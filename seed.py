import random
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm import configure_mappers
from sqlalchemy import text

from app.db import Base, engine, SessionLocal
import app.models  # подтягиваем все модели

from app.models.catalog import Seller, Category, Product, Variant
from app.models.user import User
from app.utils.security import hash_password
from app.utils.enums import UserRole
from app.models.subscriber import Subscriber
from app.models.invoice import Invoice, InvoiceItem


def run_seed():
    # === RESET ===
    Base.metadata.drop_all(bind=engine)
    print("🗑 Все таблицы удалены")

    configure_mappers()
    Base.metadata.create_all(bind=engine)
    print("✅ Все таблицы пересозданы")

    db = SessionLocal()
    try:
        # --- Продавцы ---
        sellers_data = [
            ("Магазин №1", "Алматы"),
            ("Магазин №2", "Астана"),
            ("Магазин №3", "Шымкент"),
            ("Магазин №4", "Караганда"),
            ("Магазин №5", "Костанай"),
        ]
        sellers = []
        for name, city in sellers_data:
            s = Seller(name=name, city=city)
            db.add(s)
            db.commit()
            sellers.append(s)
            print(f"✅ Продавец создан: {name} ({city})")

        # --- Категории и товары ---
        categories_with_products = {
            "Сыромолочные": [
                "Сыр Пармезан", "Сыр Чеддер", "Сметана", "Молоко", "Йогурт", "Сливки", "Масло сливочное"
            ],
            "Мясо": [
                "Колбаса куриная", "Говядина стейк", "Куриное филе", "Фарш говяжий", "Пельмени", "Сосиски молочные"
            ],
            "Овощи и фрукты": [
                "Яблоки", "Картофель", "Огурцы свежие", "Помидоры", "Капуста", "Перец", "Бананы", "Апельсины"
            ],
            "Напитки": [
                "Минеральная вода", "Сок яблочный", "Сок апельсиновый", "Кофе", "Чай черный", "Фанта", "Кола"
            ],
            "Бытовые товары": [
                "Мыло", "Шампунь", "Средство для посуды", "Губки кухонные", "Туалетная бумага", "Порошок"
            ],
        }

        products = []
        for cat_name, prod_list in categories_with_products.items():
            category = Category(name=cat_name, slug=cat_name.lower().replace(" ", "_"))
            db.add(category)
            db.commit()
            db.refresh(category)
            print(f"✅ Категория создана: {category.name}")

            for pname in prod_list:
                seller = random.choice(sellers)
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

                cost = Decimal(random.randint(200, 2000))
                price = cost + Decimal(random.randint(100, 800))

                variant = Variant(
                    product_id=product.id,
                    name="Основной вариант",
                    pack_size=1,
                    unit_price=price,
                    unit_price_net_cost=cost,
                    stock=random.randint(20, 150),
                    is_active=True,
                )
                db.add(variant)
                db.commit()
                products.append((product, variant))
                print(f"✅ Товар создан: {product.name} ({seller.name})")

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
        channel_chat_id = "1355132132"  # твой Telegram ID
        subscriber = Subscriber(chat_id=channel_chat_id, username="shop_channel", chat_type="analytics")
        db.add(subscriber)
        db.commit()
        print(f"✅ Канал добавлен как подписчик: {channel_chat_id}")

        # === 📦 Генерация тестовых продаж ===
        print("📦 Генерируем тестовые накладные и продажи...")
        today = datetime.now()
        cities = ["Алматы", "Астана", "Шымкент", "Караганда", "Костанай", "Актобе", "Павлодар"]

        for d in range(30):  # 30 дней продаж
            for _ in range(random.randint(3, 10)):  # 3–10 накладных в день
                invoice_date = today - timedelta(days=d)
                seller = random.choice(sellers)
                city = random.choice(cities)

                # ✅ исправлено: убран seller_id
                invoice = Invoice(
                    customer_name=f"Покупатель {random.randint(1, 500)}",
                    seller_name=seller.name,
                    city_name=city,
                    created_at=invoice_date,
                    status=random.choice(["new", "packed", "shipped", "delivered"]),
                    is_paid=True
                )
                db.add(invoice)
                db.commit()
                db.refresh(invoice)

                # ✅ 3–12 случайных товаров на накладную
                for _ in range(random.randint(3, 12)):
                    product, variant = random.choice(products)
                    qty = random.randint(1, 10)
                    line_total = variant.unit_price * qty

                    item = InvoiceItem(
                        invoice_id=invoice.id,
                        seller_id=seller.id,
                        seller_name=seller.name,
                        product_id=product.id,
                        variant_id=variant.id,
                        product_name=product.name,
                        variant_name=variant.name,
                        product_image=None,
                        qty_original=qty,
                        qty_final=qty,
                        unit_price_net_cost=variant.unit_price_net_cost,
                        unit_price_original=variant.unit_price,
                        unit_price_final=variant.unit_price,
                        line_total_original=line_total,
                        line_total_final=line_total
                    )
                    db.add(item)

                db.commit()
            print(f"✅ Продажи за {invoice_date.date()} сгенерированы")

        print("🎉 Тестовые данные успешно сгенерированы (30 дней продаж).")

    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
