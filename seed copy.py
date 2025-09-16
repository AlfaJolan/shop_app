# seed.py — идемпотентный импорт справочников (с остатками)
from typing import Optional
from decimal import Decimal

from app.db import Base, engine, SessionLocal

# ВАЖНО: импортируем модели ДО create_all, иначе таблицы не появятся
from app.models.catalog import Category, Product, Variant  # noqa
from app.models.order import Order, OrderItem  # noqa (на будущее)
from app.models.invoice import Invoice, InvoiceItem  # noqa (на будущее)

# создаём недостающие таблицы
Base.metadata.create_all(bind=engine)


def get_or_create_category(db, name: str, slug: str) -> Category:
    obj: Optional[Category] = db.query(Category).filter_by(slug=slug).first()
    if obj:
        # мягкое обновление
        if obj.name != name:
            obj.name = name
        return obj
    obj = Category(name=name, slug=slug)
    db.add(obj)
    db.flush()
    return obj


def get_or_create_product(
    db,
    name: str,
    sku: Optional[str],
    unit: str,
    image: Optional[str],
    category_id: Optional[int],
) -> Product:
    # считаем name уникальным для сида (для простоты)
    obj: Optional[Product] = db.query(Product).filter_by(name=name).first()
    if obj:
        if sku and obj.sku != sku:
            obj.sku = sku
        if unit and obj.unit != unit:
            obj.unit = unit
        if image and obj.image != image:
            obj.image = image  # например "images/milk.jpeg"
        if category_id and obj.category_id != category_id:
            obj.category_id = category_id
        return obj
    obj = Product(name=name, sku=sku, unit=unit, image=image, category_id=category_id)
    db.add(obj)
    db.flush()
    return obj


def get_or_create_variant(
    db,
    product_id: int,
    name: str,
    pack_size: int,
    unit_price: Decimal,
    stock: int,
) -> Variant:
    obj: Optional[Variant] = (
        db.query(Variant)
        .filter(Variant.product_id == product_id, Variant.name == name)
        .first()
    )
    if obj:
        # мягко обновим поля
        if obj.pack_size != pack_size:
            obj.pack_size = pack_size
        # сравниваем Decimal как строки, чтобы избежать погрешностей
        if str(obj.unit_price) != str(unit_price):
            obj.unit_price = unit_price
        if obj.stock != stock:
            obj.stock = stock
        return obj

    obj = Variant(
        product_id=product_id,
        name=name,
        pack_size=pack_size,
        unit_price=unit_price,
        stock=stock,
    )
    db.add(obj)
    db.flush()
    return obj


def main():
    db = SessionLocal()
    try:
        # 1) Категория
        cat = get_or_create_category(db, name="Продукты", slug="produkty")

        # 2) Товары (пути к изображениям — относительно app/static/)
        # кладём файлы в app/static/images/milk.jpeg и images/sugar.jpeg
        milk = get_or_create_product(
            db, name="Молоко", sku="MLK-01", unit="л", image="images/milk.jpeg", category_id=cat.id
        )
        sugar = get_or_create_product(
            db, name="Сахар", sku="SGR-01", unit="кг", image="images/sugar.jpeg", category_id=cat.id
        )

        # 3) Варианты + остатки
        get_or_create_variant(
            db, product_id=milk.id, name="1 литр", pack_size=1, unit_price=Decimal("600"), stock=100
        )
        get_or_create_variant(
            db, product_id=sugar.id, name="1 кг", pack_size=1, unit_price=Decimal("450"), stock=200
        )

        db.commit()
        print("Seed done (idempotent, with stock).")
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
