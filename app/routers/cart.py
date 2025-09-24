from typing import Dict, List
from decimal import Decimal
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse  # 🔹 добавили JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.catalog import Product, Variant
# ❌ старое:
# from app.models.order import Order, OrderItem
# ✅ новое:
from app.models.invoice import Invoice, InvoiceItem
from app.telegram.telegram_notify import notifier

# ⬇️ сервис создания накладной (оставляем твой вариант)
from app.services.invoices import create_invoice

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()

# 🔹 Helper: понять, хочет ли клиент JSON
def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "").lower()

def _get_cart(request: Request) -> Dict[str, dict]:
    return request.session.get("cart") or {}

def _set_cart(request: Request, cart: Dict[str, dict]) -> None:
    request.session["cart"] = cart

def _flash(request: Request, msg: str) -> None:
    request.session["flash"] = msg

def _pop_flash(request: Request) -> str:
    msg = request.session.get("flash")
    if "flash" in request.session:
        del request.session["flash"]
    return msg or ""

def _cart_lines(db: Session, cart: Dict[str, dict]) -> List[dict]:
    if not cart:
        return []
    variant_ids = [int(k) for k in cart.keys()]
    if not variant_ids:
        return []

    variants = db.query(Variant).filter(Variant.id.in_(variant_ids)).all()
    variants_by_id = {v.id: v for v in variants}

    product_ids = list({v.product_id for v in variants})
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    products_by_id = {p.id: p for p in products}

    lines: List[dict] = []
    for key, item in cart.items():
        vid = int(item["variant_id"])
        qty = max(0, int(item.get("qty", 1)))
        v = variants_by_id.get(vid)
        if not v:
            continue
        p = products_by_id.get(v.product_id)
        unit_price = Decimal(str(v.unit_price))
        line_total = unit_price * qty
        lines.append({
            "product_id": p.id if p else None,
            "product_name": p.name if p else f"Товар #{v.product_id}",
            "variant_id": v.id,
            "variant_name": v.name,
            "qty": qty,
            "unit_price": unit_price,
            "line_total": line_total,
            "stock": int(v.stock),
        })
    return lines

# ----------------------- ADD -----------------------
@router.post("/cart/add")
async def cart_add(
    request: Request,
    product_id: int = Form(...),
    variant_id: int = Form(...),
    qty: int = Form(1),
    db: Session = Depends(get_db)
):
    cart = _get_cart(request)
    key = str(variant_id)
    existing_qty = int(cart.get(key, {}).get("qty", 0))
    want = existing_qty + max(1, int(qty))

    v = db.query(Variant).get(int(variant_id))
    if not v:
        if _wants_json(request):
            return JSONResponse({"ok": False, "error": "Вариант не найден."}, status_code=400)
        _flash(request, "Вариант не найден.")
        return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)

    max_qty = int(v.stock)
    if max_qty <= 0:
        if _wants_json(request):
            return JSONResponse({"ok": False, "error": "Нет на складе."}, status_code=400)
        _flash(request, "Нет на складе.")
        return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)

    if want > max_qty:
        want = max_qty
        _flash(request, f"Недостаточно на складе. Установлено {want} шт.")
    else:
        _flash(request, "Товар добавлен в корзину.")

    cart[key] = {"variant_id": int(variant_id), "product_id": int(product_id), "qty": want}
    _set_cart(request, cart)

    if _wants_json(request):
        lines = _cart_lines(db, cart)
        total = sum([l["line_total"] for l in lines], Decimal("0"))
        return {
            "ok": True,
            "total_items": sum(l["qty"] for l in lines),
            "total_sum": float(total),
        }

    return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)

# ----------------------- UPDATE -----------------------
@router.post("/cart/update")
async def cart_update(
    request: Request,
    variant_id: int = Form(...),
    qty: int = Form(...),
    db: Session = Depends(get_db)
):
    cart = _get_cart(request)
    key = str(variant_id)
    updated_item = None

    if key in cart:
        new_qty = max(0, int(qty))
        v = db.query(Variant).get(int(variant_id))
        if not v:
            cart.pop(key, None)
            _set_cart(request, cart)
            if _wants_json(request):
                return JSONResponse({"ok": False, "error": "Вариант не найден"}, status_code=400)
            _flash(request, "Позиция удалена (вариант не найден).")
            return RedirectResponse(url="/cart", status_code=303)

        max_qty = int(v.stock)
        if new_qty > max_qty:
            new_qty = max_qty
            _flash(request, "Недостаточно на складе. Количество ограничено остатком.")

        if new_qty == 0:
            cart.pop(key, None)
        else:
            cart[key]["qty"] = new_qty
            updated_item = {
                "variant_id": v.id,
                "qty": new_qty,
                "line_total": float(v.unit_price) * new_qty,
            }

    _set_cart(request, cart)

    if _wants_json(request):
        lines = _cart_lines(db, cart)
        total = sum([l["line_total"] for l in lines], Decimal("0"))
        return {
            "ok": True,
            "total_items": sum(l["qty"] for l in lines),
            "total_sum": float(total),
            "updated": updated_item,
        }

    return RedirectResponse(url="/cart", status_code=303)

# ----------------------- REMOVE -----------------------
@router.post("/cart/remove")
async def cart_remove(request: Request, variant_id: int = Form(...), db: Session = Depends(get_db)):
    cart = _get_cart(request)
    removed = cart.pop(str(variant_id), None)
    _set_cart(request, cart)

    if _wants_json(request):
        lines = _cart_lines(db, cart)
        total = sum([l["line_total"] for l in lines], Decimal("0"))
        return {
            "ok": True,
            "total_items": sum(l["qty"] for l in lines),
            "total_sum": float(total),
            "removed_variant": variant_id if removed else None,
        }

    return RedirectResponse(url="/cart", status_code=303)

# ----------------------- VIEW -----------------------
@router.get("/cart", response_class=HTMLResponse)
async def cart_view(request: Request, db: Session = Depends(get_db)):
    cart = _get_cart(request)
    lines = _cart_lines(db, cart)
    total = sum([l["line_total"] for l in lines], Decimal("0"))
    flash = _pop_flash(request)
    return templates.TemplateResponse("public/cart.html", {
        "request": request,
        "lines": lines,
        "total": total,
        "flash": flash
    })

# ----------------------- CHECKOUT -----------------------
@router.post("/checkout")
async def checkout(
    request: Request,
    db: Session = Depends(get_db),
    customer_name: str = Form(""),
    phone: str = Form(""),
    seller_name: str = Form(""),
    city_name: str = Form(""),
    comment: str = Form("")
):
    cart = _get_cart(request)
    lines = _cart_lines(db, cart)
    if not lines:
        _flash(request, "Корзина пуста.")
        return RedirectResponse(url="/cart", status_code=303)

    # финальная проверка остатков
    problems = []
    for l in lines:
        v = db.query(Variant).get(int(l["variant_id"]))
        if not v or int(l["qty"]) > int(v.stock):
            problems.append(l["product_name"])

    if problems:
        _flash(request, "Недостаточно на складе по позициям: {0}. Количество скорректировано.".format(", ".join(problems)))
        for l in lines:
            v = db.query(Variant).get(int(l["variant_id"]))
            if v:
                key = str(l["variant_id"])
                cart[key]["qty"] = min(int(cart[key]["qty"]), int(v.stock))
            else:
                cart.pop(str(l["variant_id"]), None)
        _set_cart(request, cart)
        return RedirectResponse(url="/cart", status_code=303)

    # создаём накладную
    inv = create_invoice(
        db=db,
        lines=lines,
        customer_name=customer_name,
        phone=phone,
        seller_name=seller_name,
        city_name=city_name,
        comment=comment,
    )

    # списываем остатки склада
    for l in lines:
        v = db.query(Variant).get(int(l["variant_id"]))
        v.stock = int(v.stock) - int(l["qty"])
    db.commit()

    _set_cart(request, {})
    items = [
        {"name": item.product_name + ", " + item.variant_name, "qty": item.qty_original, "price": item.unit_price_original}
        for item in inv.items
    ]

    notifier.notify_invoice_created(
        invoice_id=inv.id,
        invoice_pkey=inv.pkey,
        customer_name=inv.customer_name,
        phone=inv.phone,
        comment=inv.comment,
        items=items
    )

    return RedirectResponse(
    url=f"/invoice/{inv.id}?pkey={inv.pkey}", 
    status_code=303
)

# ----------------------- SET (новый) -----------------------
@router.post("/cart/set")
async def cart_set(
    request: Request,
    product_id: int = Form(...),
    variant_id: int = Form(...),
    qty: int = Form(...),
    db: Session = Depends(get_db)
):
    """
    🔹 Новый эндпоинт: установить количество товара в корзине
    (в отличие от /cart/add, который прибавляет qty)
    """
    cart = _get_cart(request)
    key = str(variant_id)

    v = db.query(Variant).get(int(variant_id))
    if not v:
        if _wants_json(request):
            return JSONResponse({"ok": False, "error": "Вариант не найден."}, status_code=400)
        _flash(request, "Вариант не найден.")
        return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)

    max_qty = int(v.stock)
    new_qty = max(0, min(int(qty), max_qty))

    if new_qty == 0:
        cart.pop(key, None)
    else:
        cart[key] = {"variant_id": int(variant_id), "product_id": int(product_id), "qty": new_qty}

    _set_cart(request, cart)

    if _wants_json(request):
        lines = _cart_lines(db, cart)
        total = sum([l["line_total"] for l in lines], Decimal("0"))
        return {
            "ok": True,
            "total_items": sum(l["qty"] for l in lines),
            "total_sum": float(total),
        }

    return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)


# ----------------------- STATE (новый) -----------------------
@router.get("/cart/state")
async def cart_state(request: Request, db: Session = Depends(get_db)):
    """
    🔹 Новый эндпоинт: вернуть текущее состояние корзины в JSON
    Используется фронтом при загрузке страницы (для обновления UI).
    """
    cart = _get_cart(request)
    lines = _cart_lines(db, cart)
    total = sum([l["line_total"] for l in lines], Decimal("0"))
    return {
        "ok": True,
        "items": [
            {
                "variant_id": l["variant_id"],
                "qty": l["qty"],
                "product_id": l["product_id"],
                "product_name": l["product_name"],
                "variant_name": l["variant_name"],
                "unit_price": float(l["unit_price"]),
                "line_total": float(l["line_total"]),
                "stock": l["stock"],
            }
            for l in lines
        ],
        "total_items": sum(l["qty"] for l in lines),
        "total_sum": float(total),
    }

# ----------------------- CLEAR -----------------------
@router.post("/cart/clear")
async def cart_clear(request: Request, db: Session = Depends(get_db)):
    _set_cart(request, {})

    if _wants_json(request):
        return {"ok": True, "total_items": 0, "total_sum": 0, "items": []}

    return RedirectResponse(url="/cart", status_code=303)



