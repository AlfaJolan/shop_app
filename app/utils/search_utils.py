from typing import Dict, List
from app.models.catalog import Product


def product_to_dict(p: Product) -> Dict[str, any]:
    """Конвертирует объект Product в словарь для API"""
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


def _norm(s: str) -> str:
    return (s or "").casefold()


def _find_pos(text: str, q: str) -> int:
    """Позиция вхождения (0..), если нет — большое число"""
    t = _norm(text)
    i = t.find(_norm(q))
    return i if i >= 0 else 10_000


def rank_product_obj(p: Product, q: str) -> tuple:
    """
    Ключ сортировки для карточек:
      0 — товар начинается с q
      1 — товар содержит q
      2 — вариант начинается с q
      3 — вариант содержит q
      4 — категория начинается с q
      5 — категория содержит q
      9 — fallback
    """
    qn = _norm(q)
    pn = _norm(p.name)
    catn = _norm(getattr(getattr(p, "category", None), "name", ""))
    var_names = [_norm(v.name) for v in (p.variants or [])]

    if pn.startswith(qn):
        return (0, 0, len(p.name or ""))
    if qn in pn:
        return (1, _find_pos(p.name, q), len(p.name or ""))

    if any(vn.startswith(qn) for vn in var_names):
        pos = min((_find_pos(v.name, q) for v in (p.variants or [])), default=10_000)
        return (2, pos, len(p.name or ""))
    if any(qn in vn for vn in var_names):
        pos = min((_find_pos(v.name, q) for v in (p.variants or [])), default=10_000)
        return (3, pos, len(p.name or ""))

    if catn and catn.startswith(qn):
        return (4, 0, len(p.name or ""))
    if catn and qn in catn:
        return (5, _find_pos(getattr(p.category, "name", ""), q), len(p.name or ""))

    return (9, 10_000, len(p.name or ""))


def rank_suggest_item(item: Dict[str, any], q: str) -> tuple:
    """Ключ сортировки для подсказок"""
    type_weight = {"product": 0, "variant": 1, "category": 2}
    name = item.get("name") or ""
    pos = _find_pos(name, q)
    starts = 0 if _norm(name).startswith(_norm(q)) else 1
    return (starts, pos, len(name), type_weight.get(item.get("type"), 9))
