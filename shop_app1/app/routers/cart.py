from typing import Dict, List
from decimal import Decimal
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.catalog import Product, Variant
from app.models.order import Order, OrderItem
from app.telegram.telegram_notify import notifier

# ⬇️ НОВОЕ: сервис создания накладной
from app.services.invoices import create_invoice_for_order

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()

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
        _flash(request, "Вариант не найден.")
        referer = request.headers.get("referer") or "/"
        return RedirectResponse(url=referer, status_code=303)

    max_qty = int(v.stock)
    if max_qty <= 0:
        _flash(request, "Нет на складе.")
        referer = request.headers.get("referer") or "/"
        return RedirectResponse(url=referer, status_code=303)

    if want > max_qty:
        want = max_qty
        _flash(request, f"Недостаточно на складе. Установлено {want} шт.")
    else:
        _flash(request, "Товар добавлен в корзину.")

    cart[key] = {"variant_id": int(variant_id), "product_id": int(product_id), "qty": want}
    _set_cart(request, cart)

    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=303)


@router.post("/cart/update")
async def cart_update(
    request: Request,
    variant_id: int = Form(...),
    qty: int = Form(...),
    db: Session = Depends(get_db)
):
    cart = _get_cart(request)
    key = str(variant_id)
    if key in cart:
        new_qty = max(0, int(qty))
        v = db.query(Variant).get(int(variant_id))
        if not v:
            cart.pop(key, None)
            _set_cart(request, cart)
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

    _set_cart(request, cart)
    return RedirectResponse(url="/cart", status_code=303)

@router.post("/cart/remove")
async def cart_remove(request: Request, variant_id: int = Form(...)):
    cart = _get_cart(request)
    cart.pop(str(variant_id), None)
    _set_cart(request, cart)
    return RedirectResponse(url="/cart", status_code=303)

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
        # скорректируем корзину под максимальные остатки
        for l in lines:
            v = db.query(Variant).get(int(l["variant_id"]))
            if v:
                key = str(l["variant_id"])
                cart[key]["qty"] = min(int(cart[key]["qty"]), int(v.stock))
            else:
                cart.pop(str(l["variant_id"]), None)
        _set_cart(request, cart)
        return RedirectResponse(url="/cart", status_code=303)

    total = sum([l["line_total"] for l in lines], Decimal("0"))

    order = Order(
        customer_name=customer_name.strip() or None,
        phone=phone.strip() or None,
        seller_name=seller_name.strip() or None,
        city_name=city_name.strip() or None,
        comment=comment.strip() or None,
        total_amount=total
    )
    db.add(order)
    db.flush()

    # позиции + списание остатков
    for l in lines:
        db.add(OrderItem(
            order_id=order.id,
            product_id=l["product_id"] or 0,
            variant_id=l["variant_id"],
            product_name=l["product_name"],
            variant_name=l["variant_name"],
            qty=int(l["qty"]),
            unit_price=l["unit_price"],
            line_total=l["line_total"],
        ))
        v = db.query(Variant).get(int(l["variant_id"]))
        v.stock = int(v.stock) - int(l["qty"])

    db.commit()

    # ⬇️ НОВОЕ: создаём накладную и показываем ссылку на неё
    inv = create_invoice_for_order(
        db=db,
        order=order,
        lines=lines,
        customer_name=customer_name,
        phone=phone,
        seller_name=seller_name,
        city_name=city_name,
        comment=comment,
    )

    _set_cart(request, {})  # очистили корзину
    items = [
    {"name": item.product_name + ", " + item.variant_name, "qty": item.qty, "price": item.unit_price}
    for item in order.items
    ]

    notifier.notify_order_created(
    order_id=order.id,
    customer_name=order.customer_name,
    phone=order.phone,
    comment=order.comment,
    items=items
    )
    # Показываем «Заказ принят» + ссылки на накладную
    return templates.TemplateResponse("public/checkout_success.html", {
        "request": request,
        "order": order,
        "lines": lines,
        "total": total,
        "invoice_id": inv.id,
        "invoice_pkey": inv.pkey,
    })
