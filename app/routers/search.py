# app/routers/search.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Dict, Any

from app.db import get_db
from app.models.catalog import Product, Category, Variant, Seller

router = APIRouter(prefix="/search", tags=["search"])


def _q_like(q: str) -> str:
    return f"%{(q or '').strip().lower()}%"


def _product_to_dict(p: Product) -> Dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "image": p.image,
        "seller": p.seller.name if getattr(p, "seller", None) else None,
        "city": p.seller.city if getattr(p, "seller", None) and p.seller.city else None,
        "variants": [
            {
                "id": v.id,
                "name": v.name,
                "unit_price": float(v.unit_price),
                "stock": v.stock,
            } for v in (p.variants or [])
        ],
    }


@router.get("/suggest")
def suggest(q: str = Query(""), limit: int = Query(8, ge=1, le=20), db: Session = Depends(get_db)):
    """
    Автоподсказки: категории, товары, варианты.
    Возвращает [{type,id,name,url,product_id?}]
    """
    q = (q or "").strip().lower()
    if not q:
        return []
    q_like = _q_like(q)

    items: List[Dict[str, Any]] = []

    # Категории
    cats = (
        db.query(Category)
        .filter(func.lower(Category.name).like(q_like))
        .limit(limit)
        .all()
    )
    for c in cats:
        items.append({
            "type": "category",
            "id": c.id,
            "name": c.name,
            "url": f"/category/{c.id}",
        })

    # Товары
    prods = (
        db.query(Product)
        .filter(func.lower(Product.name).like(q_like))
        .limit(limit)
        .all()
    )
    for p in prods:
        items.append({
            "type": "product",
            "id": p.id,
            "name": p.name,
            "url": f"/product/{p.id}",
        })

    # Варианты
    vars = (
        db.query(Variant)
        .join(Product, Product.id == Variant.product_id)
        .filter(func.lower(Variant.name).like(q_like))
        .limit(limit)
        .all()
    )
    for v in vars:
        items.append({
            "type": "variant",
            "id": v.id,
            "name": f"{v.product.name} — {v.name}",
            "url": f"/product/{v.product_id}?variant={v.id}",
            "product_id": v.product_id,
        })

    # Можно добавить простую сортировку: точнее вхождение и короче строка
    def _rank(name: str) -> tuple[int, int]:
        lo = (name or "").lower()
        pos = lo.find(q)
        pos = pos if pos >= 0 else 9999
        return (pos, len(name or ""))

    items.sort(key=lambda it: _rank(it["name"]))
    return items[:limit]


@router.get("/products")
def search_products(
    q: str = Query(""),
    selected_type: Optional[str] = Query(None, description="product|variant|category"),
    selected_id: Optional[int] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Динамическая выдача карточек:
    - Если selected_type+selected_id заданы:
        product  -> один товар по id
        variant  -> один товар по id варианта
        category -> товары категории
    - Иначе: поиск по q (product.name | category.name | variant.name), регистронезависимо
    """
    q = (q or "").strip().lower()
    results: List[Product] = []

    if selected_type and selected_id:
        st = selected_type.lower().strip()
        if st == "product":
            p = db.query(Product).filter(Product.id == selected_id).first()
            results = [p] if p else []
        elif st == "variant":
            v = (
                db.query(Variant)
                .join(Product, Product.id == Variant.product_id)
                .filter(Variant.id == selected_id)
                .first()
            )
            results = [v.product] if v and v.product else []
        elif st == "category":
            results = (
                db.query(Product)
                .filter(Product.category_id == selected_id)
                .limit(limit)
                .all()
            )
        else:
            results = []
    else:
        if not q:
            # без q возвращаем пусто (пусть на странице показывается дефолтный каталог)
            return []
        q_like = _q_like(q)
        # поиск по имени товара, категории и варианта
        results = (
            db.query(Product)
            .join(Category, Category.id == Product.category_id, isouter=True)
            .join(Variant, Variant.product_id == Product.id, isouter=True)
            .filter(
                (func.lower(Product.name).like(q_like)) |
                (func.lower(Category.name).like(q_like)) |
                (func.lower(Variant.name).like(q_like))
            )
            .distinct(Product.id)
            .limit(limit)
            .all()
        )

    return [_product_to_dict(p) for p in results if p]
