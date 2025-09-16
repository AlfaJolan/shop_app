# scripts/reset_and_seed.py
from app.db import Base, engine, SessionLocal
import random
import app.models  # важно: подтягиваем все модели
from sqlalchemy.orm import configure_mappers
from decimal import Decimal
from app.models.catalog import Seller, Category, Product, Variant

def run_seed():
      # === RESET ===
    Base.metadata.drop_all(bind=engine)
    print("🗑 Все таблицы удалены")

    configure_mappers()
    Base.metadata.create_all(bind=engine)
    print("✅ Все таблицы пересозданы")

    db = SessionLocal()
    try:
        # --- 1. Продавец ---
        seller = Seller(name="Магазин №1", city="Алматы")
        db.add(seller)
        db.commit()
        db.refresh(seller)
        print(f"✅ Продавец создан: {seller.name}")

        # --- 2. Категории (несколько штук) ---
        category_names = [
            "Продукты", "Молочные", "Напитки", "Крупы", "Бакалея",
            "Сладости", "Овощи", "Фрукты"
        ]
        categories = []
        for i, nm in enumerate(category_names, start=1):
            category = Category(name=nm, slug=f"cat-{i}")  # простой slug, без транслита
            db.add(category)
            db.commit()
            db.refresh(category)
            categories.append(category)
            print(f"✅ Категория создана: {category.name}")

        # --- 3. Наборы имён товаров и вариантов ---
        product_bases = [
            "Молоко", "Сахар", "Соль", "Мука", "Рис", "Гречка", "Яйца",
            "Сыр", "Колбаса", "Йогурт", "Сметана", "Творог", "Масло",
            "Кефир", "Кофе", "Чай", "Вода", "Сок", "Печенье", "Шоколад",
            "Чипсы", "Кукуруза консервированная", "Горошек консервированный",
            "Тунец", "Сардина"
        ]
        adjectives = ["деревенское", "фермерское", "отборное", "классическое", "ультра", "натуральное"]
        units = ["шт", "кг", "л", "упак."]

        variant_weights = ["300 г", "400 г", "450 г", "500 г", "700 г", "900 г", "1 кг", "2 кг"]
        variant_volumes = ["0.33 л", "0.5 л", "0.9 л", "1 л", "1.5 л", "2 л"]
        variant_fat = ["1%", "2.5%", "3.2%", "5%"]
        variant_packs = ["упаковка 4 шт", "упаковка 6 шт", "упаковка 12 шт"]

        def random_price():
            return Decimal(f"{random.uniform(150, 4000):.2f}")

        def random_stock():
            # иногда 0, чтобы проверить «нет в наличии»
            return random.choice([0] + [random.randint(1, 120) for _ in range(9)])

        def make_product_name():
            base = random.choice(product_bases)
            if random.random() < 0.5:
                base = f"{base} {random.choice(adjectives)}"
            # Чуть-чуть «ломаем» регистр для проверки регистронезависимого поиска
            if random.random() < 0.2:
                base = "".join(ch.upper() if i % 2 else ch.lower() for i, ch in enumerate(base))
            return base

        def pick_variant_name(prod_name: str):
            pool = variant_weights + variant_volumes + variant_packs
            if any(x in prod_name.lower() for x in ["молоко", "йогурт", "кефир", "сметана"]):
                pool = pool + variant_fat
            return random.choice(pool)

        # --- 4. Товары + Варианты ---
        # Сколько товаров хотим нагенерить (можешь менять)
        TOTAL_PRODUCTS = 120
        # Сколько вариантов на каждый товар (минимум/максимум)
        MIN_VARIANTS = 2
        MAX_VARIANTS = 5

        for idx in range(1, TOTAL_PRODUCTS + 1):
            # Товар
            p = Product(
                name=make_product_name(),
                sku=f"SKU{idx:05d}",
                unit=random.choice(units),
                image=None,          # можно подставить файл, если есть
                is_active=True,
                category_id=random.choice(categories).id,
                seller_id=seller.id,
            )
            db.add(p)
            db.flush()  # чтобы появился p.id
            print(f"✅ Товар создан: {p.name}")

            # Варианты для товара
            used_names = set()
            variants_to_add = random.randint(MIN_VARIANTS, MAX_VARIANTS)
            for _ in range(variants_to_add):
                vn = pick_variant_name(p.name)
                # избегаем дублей вариантов одного товара
                tries = 0
                while vn in used_names and tries < 5:
                    vn = pick_variant_name(p.name)
                    tries += 1
                used_names.add(vn)

                v = Variant(
                    product_id=p.id,
                    name=vn,
                    pack_size=1,
                    unit_price=random_price(),
                    stock=random_stock(),
                    is_active=True,
                )
                db.add(v)

            db.commit()
            print("✅ Варианты добавлены")

        print("🎉 Готово: БД заполнена тестовыми товарами и вариантами.")

    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
