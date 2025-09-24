from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List, Dict, Any

from app.db import get_db
from app.models.catalog import Product, Category, Variant
from app.utils.search_utils import product_to_dict, rank_product_obj, rank_suggest_item

router = APIRouter(prefix="/search", tags=["search"])


# =========================
# /search/suggest
# =========================

@router.get("/suggest")
def suggest(
    q: str = Query(""),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    q = (q or "").strip()
    if not q:
        return []

    items: List[Dict[str, Any]] = []

    # Категории
    cats = (
        db.query(Category)
        .filter(Category.name.ilike(f"%{q}%"))
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
        .filter(Product.name.ilike(f"%{q}%"))
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
    vars_ = (
        db.query(Variant)
        .join(Product, Product.id == Variant.product_id)
        .filter(Variant.name.ilike(f"%{q}%"))
        .limit(limit)
        .all()
    )
    for v in vars_:
        items.append({
            "type": "variant",
            "id": v.id,
            "name": f"{v.product.name} — {v.name}",
            "url": f"/product/{v.product_id}?variant={v.id}",
            "product_id": v.product_id,
        })

    items.sort(key=lambda it: rank_suggest_item(it, q))
    return items[:limit]


# =========================
# /search/products
# =========================

@router.get("/products")
def search_products(
    q: str = Query(""),
    selected_type: Optional[str] = Query(None, description="product|variant|category"),
    selected_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),   # 🔹 добавили фильтр по категории
    # 🔹 Пагинация (необязательно). Если page не передан — вернём список как раньше.
    page: Optional[int] = Query(None, ge=1),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = (q or "").strip()
    results: List[Product] = []

    # Если пользователь выбрал конкретный объект (товар/вариант/категорию)
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
        return [product_to_dict(p) for p in results if p]

    # ===== РЕЖИМ БЕЗ ПАГИНАЦИИ (поведение как раньше) =====
    if page is None:
        # Если нет запроса и категории → вернуть пусто
        # Если нет запроса и категории → вернуть пусто
        if not q and not category_id:
            results = db.query(Product).limit(limit).all()
            return [product_to_dict(p) for p in results if p]

        # Базовый запрос
        candidates = (
            db.query(Product)
            .join(Category, Category.id == Product.category_id, isouter=True)
            .join(Variant, Variant.product_id == Product.id, isouter=True)
        )

        # Фильтрация по поисковому запросу
        if q:
            candidates = candidates.filter(
                or_(
                    Product.name.ilike(f"%{q}%"),
                    Category.name.ilike(f"%{q}%"),
                    Variant.name.ilike(f"%{q}%"),
                )
            )

        # 🔹 Фильтрация по категории (если выбрана)
        if category_id:
            candidates = candidates.filter(Product.category_id == category_id)

        # Ограничение и сортировка
        candidates = candidates.distinct(Product.id).limit(max(limit * 4, 200)).all()
        candidates.sort(key=lambda p: rank_product_obj(p, q))
        results = candidates[:limit]

        return [product_to_dict(p) for p in results if p]

    # ===== РЕЖИМ С ПАГИНАЦИЕЙ (page передан) =====
    # Здесь возвращаем объект с meta: items, page, limit, total_items, total_pages

    # Базовый запрос для кандидатов
    base_q = (
        db.query(Product)
        .join(Category, Category.id == Product.category_id, isouter=True)
        .join(Variant, Variant.product_id == Product.id, isouter=True)
    )

    if q:
        base_q = base_q.filter(
            or_(
                Product.name.ilike(f"%{q}%"),
                Category.name.ilike(f"%{q}%"),
                Variant.name.ilike(f"%{q}%"),
            )
        )
    if category_id:
        base_q = base_q.filter(Product.category_id == category_id)

    # Важный момент: чтобы сохранить твою ранжировку rank_product_obj,
    # мы получим все кандидаты (distinct), отсортируем в Python и уже потом порежем на страницы.
    # Да, для очень больших выборок это тяжелее, но поведение будет 1-в-1 как раньше, только постранично.

    candidates_all = base_q.distinct(Product.id).all()
    total_items = len(candidates_all)

    # Сортируем как и раньше
    candidates_all.sort(key=lambda p: rank_product_obj(p, q))

    # Режем по страницам
    current_page = page or 1
    start = (current_page - 1) * limit
    end = start + limit
    page_items = candidates_all[start:end]

    return {
        "items": [product_to_dict(p) for p in page_items if p],
        "page": current_page,
        "limit": limit,
        "total_items": total_items,
        "total_pages": (total_items + limit - 1) // limit
    }
