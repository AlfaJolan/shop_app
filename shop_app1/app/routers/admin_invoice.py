# app/routers/admin_invoice.py
from decimal import Decimal, InvalidOperation
from typing import Optional, List

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.invoice import Invoice, InvoiceItem
from app.models.invoice_audit import InvoiceAudit  # Убедись, что этот модуль импортируется в app/models/__init__.py
from app.models.catalog import Variant  # 🔹 импорт для работы со складом

templates = Jinja2Templates(directory="app/templates")

# Префикс для всех маршрутов админки накладных
router = APIRouter(prefix="/admin/invoices", tags=["admin-invoices"])


def _dec(val: str, default: Decimal) -> Decimal:
    """Безопасный парсинг десятичного числа с поддержкой запятой."""
    if val is None:
        return default
    val = val.replace(",", ".").strip()
    try:
        return Decimal(val)
    except (InvalidOperation, ValueError):
        return default


@router.get("/{invoice_id}", response_class=HTMLResponse)
def invoice_short(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Поддержка короткого пути /admin/invoices/{id} — редирект на /edit.
    Чтобы не ловить 404, если пользователь не дописал '/edit'.
    """
    inv: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")
    return RedirectResponse(url=f"/admin/invoices/{invoice_id}/edit", status_code=303)


@router.get("/{invoice_id}/edit", response_class=HTMLResponse)
def edit_invoice(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    """
    Страница редактирования накладной:
    - изменение qty_final и unit_price_final по позициям,
    - показ зачёркнутого original → жирного final,
    - автоматический пересчёт сумм.
    """
    inv: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")
    return templates.TemplateResponse("admin/invoice_edit.html", {
        "request": request,
        "inv": inv,
        "items": inv.items,
    })


@router.post("/{invoice_id}/update", response_class=HTMLResponse)
async def update_invoice(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    """
    Применение изменений:
    - собираем значения из формы,
    - пишем аудит (кто/что/с какого на какое),
    - пересчитываем суммы строк и итог накладной,
    - 🔹 дополнительно обновляем остатки на складе (Variant.stock),
    - 🔹 если товара недостаточно — показываем ошибку прямо в форме.
    """
    inv: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    form = await request.form()
    audits: List[InvoiceAudit] = []
    changed = False

    for it in inv.items:
        qty_key = f"qty_final_{it.id}"
        price_key = f"unit_price_final_{it.id}"

        qty_val = form.get(qty_key, None)
        price_val = form.get(price_key, None)

        new_qty = it.qty_final
        new_price = it.unit_price_final

        # qty_final
        if qty_val is not None:
            try:
                v = int(qty_val)
                if v < 0:
                    v = 0
                new_qty = v
            except ValueError:
                pass

        # unit_price_final
        if price_val is not None:
            v = _dec(price_val, it.unit_price_final)
            if v < 0:
                v = Decimal("0")
            new_price = v

        # аудит qty + проверка склада
        if int(new_qty) != int(it.qty_final):
            delta = new_qty - it.qty_final  # разница между старым и новым количеством

            # 🔹 обязательно должен быть variant_id
            if not getattr(it, "variant_id", None):
                return templates.TemplateResponse(
                    "admin/invoice_edit.html",
                    {
                        "request": request,
                        "inv": inv,
                        "items": inv.items,
                        "error": f"Ошибка: у позиции '{it.product_name}' нет variant_id, нельзя обновить склад."
                    }
                )

            variant = db.query(Variant).get(it.variant_id)
            if not variant:
                return templates.TemplateResponse(
                    "admin/invoice_edit.html",
                    {
                        "request": request,
                        "inv": inv,
                        "items": inv.items,
                        "error": f"Ошибка: вариант товара для '{it.product_name}' не найден."
                    }
                )

            # 🔹 если увеличиваем количество — проверяем склад
            if delta > 0 and variant.stock < delta:
                return templates.TemplateResponse(
                    "admin/invoice_edit.html",
                    {
                        "request": request,
                        "inv": inv,
                        "items": inv.items,
                        "error": f"Недостаточно товара '{variant.name}'. На складе {variant.stock}, требуется +{delta}."
                    }
                )

            # только после проверки обновляем остатки
            variant.stock -= delta

            # аудит qty
            audits.append(InvoiceAudit(
                invoice_id=inv.id,
                item_id=it.id,
                field="qty",
                old_value=Decimal(str(it.qty_final)),
                new_value=Decimal(str(new_qty)),
                user="admin",
            ))
            it.qty_final = int(new_qty)
            changed = True

        # аудит цены
        if Decimal(str(new_price)) != Decimal(str(it.unit_price_final)):
            audits.append(InvoiceAudit(
                invoice_id=inv.id,
                item_id=it.id,
                field="price",
                old_value=Decimal(str(it.unit_price_final)),
                new_value=Decimal(str(new_price)),
                user="admin",
            ))
            it.unit_price_final = new_price
            changed = True

        # пересчёт суммы строки
        it.recompute_line()

    # пересчёт итога накладной
    inv.recompute_totals()

    if changed and audits:
        for a in audits:
            db.add(a)

    db.commit()
    return RedirectResponse(url=f"/admin/invoices/{inv.id}/edit", status_code=303)


@router.post("/{invoice_id}/reset-item/{item_id}")
def reset_item(invoice_id: int, item_id: int, db: Session = Depends(get_db)):
    """
    Сброс одной строки к оригинальным qty/price (и аудит изменений).
    🔹 Дополнительно: корректируем склад (возвращаем разницу на Variant.stock).
    """
    inv: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    it: Optional[InvoiceItem] = db.query(InvoiceItem).get(item_id)
    if not it or it.invoice_id != inv.id:
        raise HTTPException(status_code=404, detail="Позиция не найдена")

    # аудит qty
    if int(it.qty_final) != int(it.qty_original):
        db.add(InvoiceAudit(
            invoice_id=inv.id,
            item_id=it.id,
            field="qty",
            old_value=Decimal(str(it.qty_final)),
            new_value=Decimal(str(it.qty_original)),
            user="admin",
        ))
    # аудит price
    if Decimal(str(it.unit_price_final)) != Decimal(str(it.unit_price_original)):
        db.add(InvoiceAudit(
            invoice_id=inv.id,
            item_id=it.id,
            field="price",
            old_value=Decimal(str(it.unit_price_final)),
            new_value=Decimal(str(it.unit_price_original)),
            user="admin",
        ))

    # 🔹 корректировка склада при сбросе
    delta = it.qty_original - it.qty_final
    if getattr(it, "variant_id", None):
        variant = db.query(Variant).get(it.variant_id)
        if variant:
            variant.stock += delta

    # сброс значений
    it.qty_final = it.qty_original
    it.unit_price_final = it.unit_price_original
    it.recompute_line()

    # пересчёт итога
    inv.recompute_totals()
    db.commit()

    return RedirectResponse(url=f"/admin/invoices/{inv.id}/edit", status_code=303)
