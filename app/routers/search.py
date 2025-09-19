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
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = (q or "").strip()
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
        return [product_to_dict(p) for p in results if p]

    if not q:
        return []

    candidates = (
        db.query(Product)
        .join(Category, Category.id == Product.category_id, isouter=True)
        .join(Variant, Variant.product_id == Product.id, isouter=True)
        .filter(
            or_(
                Product.name.ilike(f"%{q}%"),
                Category.name.ilike(f"%{q}%"),
                Variant.name.ilike(f"%{q}%"),
            )
        )
        .distinct(Product.id)
        .limit(max(limit * 4, 200))
        .all()
    )

    candidates.sort(key=lambda p: rank_product_obj(p, q))
    results = candidates[:limit]

    return [product_to_dict(p) for p in results if p]
