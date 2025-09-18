# app/routers/search.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List, Dict, Any

from app.db import get_db
from app.models.catalog import Product, Category, Variant

router = APIRouter(prefix="/search", tags=["search"])


# =========================
# Helpers
# =========================

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


def _patterns(q: str) -> List[str]:
    """
    Для SQLite: формируем несколько регистровых вариантов под LIKE,
    т.к. LOWER/ILIKE для кириллицы там работают ненадёжно.
    """
    q = (q or "").strip()
    if not q:
        return []
    variants = [q, q.lower(), q.upper(), q.capitalize(), q.title()]
    seen, out = set(), []
    for s in variants:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return [f"%{s}%" for s in out]


def _ci_like(col, q: str, is_sqlite: bool):
    """
    Кросс-СУБД регистронезависимое сравнение:
    - SQLite: OR по нескольким LIKE c разными регистрами (см. _patterns)
    - PostgreSQL / прочие: ILIKE
    """
    if is_sqlite:
        pats = _patterns(q)
        return or_(*[col.like(p) for p in pats]) if pats else (col == None)  # noqa: E711
    else:
        return col.ilike(f"%{(q or '').strip()}%")


def _norm(s: str) -> str:
    return (s or "").casefold()


def _find_pos(text: str, q: str) -> int:
    """позиция вхождения (0..), если нет — большое число"""
    t = _norm(text)
    i = t.find(_norm(q))
    return i if i >= 0 else 10_000


def _rank_product_obj(p: Product, q: str) -> tuple:
    """
    Ключ сортировки для карточек (меньше — выше):
      0 — товар начинается с q
      1 — товар содержит q
      2 — вариант начинается с q
      3 — вариант содержит q
      4 — категория начинается с q
      5 — категория содержит q
      9 —fallback
    Далее: позиция вхождения, затем длина названия товара
    """
    qn = _norm(q)
    pn = _norm(p.name)
    catn = _norm(getattr(getattr(p, "category", None), "name", ""))
    var_names = [_norm(v.name) for v in (p.variants or [])]

    # 0/1: товар
    if pn.startswith(qn):
        return (0, 0, len(p.name or ""))
    if qn in pn:
        return (1, _find_pos(p.name, q), len(p.name or ""))

    # 2/3: варианты
    if any(vn.startswith(qn) for vn in var_names):
        pos = min((_find_pos(v.name, q) for v in (p.variants or [])), default=10_000)
        return (2, pos, len(p.name or ""))
    if any(qn in vn for vn in var_names):
        pos = min((_find_pos(v.name, q) for v in (p.variants or [])), default=10_000)
        return (3, pos, len(p.name or ""))

    # 4/5: категория
    if catn and catn.startswith(qn):
        return (4, 0, len(p.name or ""))
    if catn and qn in catn:
        return (5, _find_pos(getattr(p.category, "name", ""), q), len(p.name or ""))

    return (9, 10_000, len(p.name or ""))


def _rank_suggest_item(item: Dict[str, Any], q: str) -> tuple:
    """
    Ключ сортировки для подсказок:
      сначала префикс (начинается с q), затем позиция, затем длина,
      затем при равенстве типов — product < variant < category
    """
    type_weight = {"product": 0, "variant": 1, "category": 2}
    name = item.get("name") or ""
    pos = _find_pos(name, q)
    starts = 0 if _norm(name).startswith(_norm(q)) else 1
    return (starts, pos, len(name), type_weight.get(item.get("type"), 9))


# =========================
# /search/suggest — автоподсказки
# =========================

@router.get("/suggest")
def suggest(
    q: str = Query(""),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Автоподсказки: категории, товары, варианты.
    Выдаёт [{type,id,name,url,product_id?}]
    """
    q = (q or "").strip()
    if not q:
        return []

    is_sqlite = bool(getattr(db.bind, "dialect", None) and db.bind.dialect.name == "sqlite")

    items: List[Dict[str, Any]] = []

    # Категории
    cats = (
        db.query(Category)
        .filter(_ci_like(Category.name, q, is_sqlite))
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
        .filter(_ci_like(Product.name, q, is_sqlite))
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
        .filter(_ci_like(Variant.name, q, is_sqlite))
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

    # Ранжируем: префикс > contains, короче — лучше, product > variant > category
    items.sort(key=lambda it: _rank_suggest_item(it, q))
    return items[:limit]


# =========================
# /search/products — карточки для низа страницы
# =========================

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
    q = (q or "").strip()
    results: List[Product] = []

    is_sqlite = bool(getattr(db.bind, "dialect", None) and db.bind.dialect.name == "sqlite")

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
        return [_product_to_dict(p) for p in results if p]

    # Свободный поиск
    if not q:
        return []

    # Берём побольше кандидатов, затем ранжируем умно в Python
    candidates = (
        db.query(Product)
        .join(Category, Category.id == Product.category_id, isouter=True)
        .join(Variant, Variant.product_id == Product.id, isouter=True)
        .filter(
            or_(
                _ci_like(Product.name, q, is_sqlite),
                _ci_like(Category.name, q, is_sqlite),
                _ci_like(Variant.name, q, is_sqlite),
            )
        )
        .distinct(Product.id)
        .limit(max(limit * 4, 200))
        .all()
    )

    candidates.sort(key=lambda p: _rank_product_obj(p, q))
    results = candidates[:limit]

    return [_product_to_dict(p) for p in results if p]
