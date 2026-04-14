from typing import Dict, List
from decimal import Decimal
from fastapi import APIRouter, Request, Form, Depends, UploadFile, File, BackgroundTasks  # 🧾 NEW + background
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse  # 🔹 добавили JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from app.models.salesperson import Salesperson

from app.db import get_db
from app.models.catalog import Product, Variant
# ❌ старое:
# from app.models.order import Order, OrderItem
# ✅ новое:
from app.telegram.telegram_notify import notifier

# ⬇️ сервис создания накладной (оставляем твой вариант)
# 🔹 NEW: checkout вынесен в отдельный сервис, чтобы накладная, склад, аудит и чеки шли одной транзакцией
from app.services.checkout_service import (
    CheckoutService,
    CheckoutInput,
    CheckoutLineInput,
    CheckoutError,
)

from app.services.audit import get_actor

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

# 🔹 Оптимизация: отдельный helper для пакетной загрузки вариантов
def _load_variants_map(db: Session, variant_ids: List[int]) -> Dict[int, Variant]:
    if not variant_ids:
        return {}

    # 🔹 Подгружаем product одним запросом, чтобы не делать второй запрос на Product
    variants = (
        db.query(Variant)
        .options(joinedload(Variant.product))
        .filter(Variant.id.in_(variant_ids))
        .all()
    )
    return {v.id: v for v in variants}

def _cart_lines(db: Session, cart: Dict[str, dict]) -> List[dict]:
    if not cart:
        return []
    variant_ids = [int(k) for k in cart.keys()]
    if not variant_ids:
        return []

    # 🔹 Оптимизация: загружаем Variant + Product одним запросом
    variants_by_id = _load_variants_map(db, variant_ids)

    lines: List[dict] = []
    for key, item in cart.items():
        vid = int(item["variant_id"])
        qty = max(0, int(item.get("qty", 1)))
        v = variants_by_id.get(vid)
        if not v:
            continue

        # 🔹 Пропускаем архивные варианты и товары
        if not v.is_active or not v.product or not v.product.is_active:
            continue

        # 🔹 product уже подгружен через joinedload
        p = v.product
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

# 🔹 Новый helper: очистка корзины от архивных / удалённых позиций
def _cleanup_cart(db: Session, request: Request) -> Dict[str, dict]:
    cart = _get_cart(request)
    if not cart:
        return cart

    variant_ids = [int(k) for k in cart.keys()]
    variants_by_id = _load_variants_map(db, variant_ids)

    cleaned_cart: Dict[str, dict] = {}
    removed_any = False

    for key, item in cart.items():
        vid = int(item["variant_id"])
        v = variants_by_id.get(vid)

        if not v:
            removed_any = True
            continue

        if not v.is_active or not v.product or not v.product.is_active:
            removed_any = True
            continue

        cleaned_cart[key] = item

    if removed_any:
        _set_cart(request, cleaned_cart)

    return cleaned_cart

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

    # 🔹 Оптимизация: db.get быстрее и чище, чем query(...).get(...)
    v = db.get(Variant, int(variant_id))
    if not v:
        if _wants_json(request):
            return JSONResponse({"ok": False, "error": "Вариант не найден."}, status_code=400)
        _flash(request, "Вариант не найден.")
        return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)

    # 🔹 Защита от архивных товаров и вариантов
    p = db.get(Product, int(product_id))
    if not v.is_active or not p or not p.is_active or int(v.product_id) != int(product_id):
        if _wants_json(request):
            return JSONResponse({"ok": False, "error": "Товар больше недоступен."}, status_code=400)
        _flash(request, "Товар больше недоступен.")
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
        cart = _cleanup_cart(db, request)
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
        v = db.get(Variant, int(variant_id))
        if not v:
            cart.pop(key, None)
            _set_cart(request, cart)
            if _wants_json(request):
                return JSONResponse({"ok": False, "error": "Вариант не найден"}, status_code=400)
            _flash(request, "Позиция удалена (вариант не найден).")
            return RedirectResponse(url="/cart", status_code=303)

        # 🔹 Если вариант или товар архивирован — удаляем позицию из корзины
        p = db.get(Product, int(v.product_id))
        if not v.is_active or not p or not p.is_active:
            cart.pop(key, None)
            _set_cart(request, cart)
            if _wants_json(request):
                return JSONResponse({"ok": False, "error": "Товар больше недоступен"}, status_code=400)
            _flash(request, "Позиция удалена (товар больше недоступен).")
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
        cart = _cleanup_cart(db, request)
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
        cart = _cleanup_cart(db, request)
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
    cart = _cleanup_cart(db, request)
    lines = _cart_lines(db, cart)
    total = sum([l["line_total"] for l in lines], Decimal("0"))
    flash = _pop_flash(request)

    # Получаем список продавцов для выбора в форме
    salespersons = db.query(Salesperson).order_by(Salesperson.name.asc()).all()

    return templates.TemplateResponse("public/cart.html", {
        "request": request,
        "lines": lines,
        "total": total,
        "flash": flash,
        "salespersons": salespersons,  # 👈 передаём в шаблон
    })

# ----------------------- CHECKOUT -----------------------
@router.post("/checkout")
async def checkout(
    request: Request,
    background_tasks: BackgroundTasks,  # 🔹 добавили фоновую отправку Telegram
    db: Session = Depends(get_db),
    customer_name: str = Form(""),
    phone: str = Form(""),
    seller_name: str = Form(""),
    salesperson_id: int = Form(None),  # 🔹 добавили
    city_name: str = Form(""),
    comment: str = Form(""),
    files: list[UploadFile] = File(None)  # 🧾 NEW — файлы чеков (опционально)
):
    """
    Универсальная форма:
    - если чек не прикреплён → обычная накладная
    - если чек прикреплён → накладная + InvoiceReceipt
    """
    cart = _cleanup_cart(db, request)
    lines = _cart_lines(db, cart)
    if not lines:
        _flash(request, "Корзина пуста.")
        return RedirectResponse(url="/cart", status_code=303)

    # 🔹 NEW: получаем того, кто оформил заказ
    actor = get_actor(request, db)

    # 🔹 NEW: переводим строки корзины в формат нового checkout-сервиса
    checkout_lines = [
        CheckoutLineInput(
            product_id=l["product_id"],
            product_name=l["product_name"],
            variant_id=l["variant_id"],
            variant_name=l["variant_name"],
            qty=l["qty"],
            unit_price=l["unit_price"],
            line_total=l["line_total"],
        )
        for l in lines
    ]

    # 🔹 NEW: теперь весь checkout выполняется внутри отдельного сервиса одной транзакцией
    service = CheckoutService(db)

    try:
        result = await service.checkout(
            CheckoutInput(
                customer_name=customer_name,
                phone=phone,
                seller_name=seller_name,
                salesperson_id=salesperson_id,  # 🔹 передаём выбранного продавца
                city_name=city_name,
                comment=comment,
                lines=checkout_lines,
                receipt_files=files or [],
            ),
            actor=actor,
        )
    except CheckoutError as e:
        # 🔹 NEW: контролируемые ошибки checkout показываем пользователю
        _flash(request, str(e))
        return RedirectResponse(url="/cart", status_code=303)

    # стандартное уведомление, если чек не прикреплён
    items = result.items

    # 🔹 Оптимизация: Telegram отправляем в фоне, чтобы не тормозить checkout
    background_tasks.add_task(
        notifier.notify_invoice_created,
        invoice_id=result.invoice_id,
        invoice_pkey=result.invoice_pkey,
        customer_name=result.customer_name,
        phone=result.phone,
        comment=result.comment,
        items=items
    )

    _set_cart(request, {})

    return RedirectResponse(
        url=f"/invoice/{result.invoice_id}?pkey={result.invoice_pkey}",
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

    v = db.get(Variant, int(variant_id))
    if not v:
        if _wants_json(request):
            return JSONResponse({"ok": False, "error": "Вариант не найден."}, status_code=400)
        _flash(request, "Вариант не найден.")
        return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)

    # 🔹 Защита от архивных товаров и вариантов
    p = db.get(Product, int(product_id))
    if not v.is_active or not p or not p.is_active or int(v.product_id) != int(product_id):
        cart.pop(key, None)
        _set_cart(request, cart)
        if _wants_json(request):
            return JSONResponse({"ok": False, "error": "Товар больше недоступен."}, status_code=400)
        _flash(request, "Товар больше недоступен.")
        return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)

    max_qty = int(v.stock)
    new_qty = max(0, min(int(qty), max_qty))

    if new_qty == 0:
        cart.pop(key, None)
    else:
        cart[key] = {"variant_id": int(variant_id), "product_id": int(product_id), "qty": new_qty}

    _set_cart(request, cart)

    if _wants_json(request):
        cart = _cleanup_cart(db, request)
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
    cart = _cleanup_cart(db, request)
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