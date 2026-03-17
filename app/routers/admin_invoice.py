# app/routers/admin_invoice.py
from decimal import Decimal, InvalidOperation
from typing import Optional, List

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.invoice import Invoice, InvoiceItem, InvoiceReceipt
from app.models.invoice_audit import InvoiceAudit  # Убедись, что этот модуль импортируется в app/models/__init__.py
from app.models.catalog import Variant  # 🔹 импорт для работы со складом
from datetime import datetime                  # 🆕 для отметки времени
from app.services.audit import write_audit, get_actor  # ✅ импорт для аудита


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
        "receipts": inv.receipts,   # 🆕 передаём чеки в шаблон
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

    # 🆕 Получаем текущего пользователя для общего аудита
    actor = get_actor(request, db)

    # 🆕 Снимок накладной ДО изменений.
    # Храним только полезные поля: итог и изменяемые позиции.
    old_items_map = {
        it.id: {
            "item_id": it.id,
            "variant_id": getattr(it, "variant_id", None),
            "product_name": it.product_name,
            "variant_name": it.variant_name,
            "qty_final": int(it.qty_final),
            "unit_price_final": float(it.unit_price_final) if it.unit_price_final is not None else None,
            "line_total_final": float(it.line_total_final) if getattr(it, "line_total_final", None) is not None else None,
        }
        for it in inv.items
    }
    old_total = float(getattr(inv, "total_amount_final", 0) or 0)

    # 🆕 Здесь будем собирать только реально измененные строки,
    # чтобы общий audit_log не засорялся всеми позициями накладной.
    changed_items_old = []
    changed_items_new = []

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

        # 🆕 Запоминаем старый склад до возможного изменения,
        # чтобы потом можно было положить в общий аудит.
        old_variant_stock = None
        new_variant_stock = None

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

            # 🆕 Сохраняем остаток до изменения
            old_variant_stock = int(variant.stock)

            # только после проверки обновляем остатки
            variant.stock -= delta

            # 🆕 Сохраняем остаток после изменения
            new_variant_stock = int(variant.stock)

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

        # 🆕 Если строка реально изменилась по qty и/или price,
        # добавляем ее в общий аудит с данными "до" и "после".
        if (
            int(old_items_map[it.id]["qty_final"]) != int(it.qty_final)
            or Decimal(str(old_items_map[it.id]["unit_price_final"] or 0)) != Decimal(str(it.unit_price_final or 0))
        ):
            changed_items_old.append({
                "item_id": old_items_map[it.id]["item_id"],
                "variant_id": old_items_map[it.id]["variant_id"],
                "product_name": old_items_map[it.id]["product_name"],
                "variant_name": old_items_map[it.id]["variant_name"],
                "qty_final": old_items_map[it.id]["qty_final"],
                "unit_price_final": old_items_map[it.id]["unit_price_final"],
                "line_total_final": old_items_map[it.id]["line_total_final"],
                "variant_stock": old_variant_stock,
            })
            changed_items_new.append({
                "item_id": it.id,
                "variant_id": getattr(it, "variant_id", None),
                "product_name": it.product_name,
                "variant_name": it.variant_name,
                "qty_final": int(it.qty_final),
                "unit_price_final": float(it.unit_price_final) if it.unit_price_final is not None else None,
                "line_total_final": float(it.line_total_final) if getattr(it, "line_total_final", None) is not None else None,
                "variant_stock": new_variant_stock,
            })

    # пересчёт итога накладной
    inv.recompute_totals()

    if changed and audits:
        for a in audits:
            db.add(a)

        # 🆕 Пишем одну общую запись в audit_log на все ручное редактирование накладной.
        # Старый InvoiceAudit оставляем как есть — он дает детальный аудит по qty/price,
        # а здесь будет общий журнал: кто, когда и какие строки поменял.
        write_audit(
            db=db,
            entity_type="invoice",
            entity_id=inv.id,
            action="invoice_updated",
            actor=actor,
            old_data={
                "invoice_id": inv.id,
                "total_amount_final": old_total,
                "items": changed_items_old,
            },
            new_data={
                "invoice_id": inv.id,
                "total_amount_final": float(getattr(inv, "total_amount_final", 0) or 0),
                "items": changed_items_new,
            },
            note="Ручное редактирование накладной",
        )

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

@router.post("/{invoice_id}/receipts/{receipt_id}/approve")
async def approve_receipt(invoice_id: int, receipt_id: int, request: Request, db: Session = Depends(get_db)):
    inv: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    rec: Optional[InvoiceReceipt] = db.query(InvoiceReceipt).get(receipt_id)
    if not rec or rec.invoice_id != inv.id:
        raise HTTPException(status_code=404, detail="Чек не найден")

    # 👇 получаем пользователя
    actor = get_actor(request, db)

    # 👇 сохраняем старое состояние
    old_data = {
        "status": rec.status,
        "amount": rec.amount,
    }

    form = await request.form()
    amount_str = form.get("amount")
    try:
        rec.amount = float(amount_str)
    except Exception:
        rec.amount = None

    rec.status = "approved"
    
 # если хотя бы один чек approved → ставим is_paid=True
    #inv.is_paid = True
    #inv.status = "paid"
    #inv.status_changed_at = datetime.utcnow()
    # 👇 новое состояние
    new_data = {
        "status": rec.status,
        "amount": rec.amount,
        "invoice_id": inv.id,
    }

    # 👇 пишем аудит
    write_audit(
        db=db,
        entity_type="receipt",
        entity_id=rec.id,
        action="receipt_approved",
        actor=actor,
        old_data=old_data,
        new_data=new_data,
        note="Чек подтвержден",
    )

    db.commit()
    return RedirectResponse(url=f"/admin/invoices/{inv.id}/edit", status_code=303)


@router.post("/{invoice_id}/receipts/{receipt_id}/reject")
async def reject_receipt(invoice_id: int, receipt_id: int, request: Request, db: Session = Depends(get_db)):
    inv: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    rec: Optional[InvoiceReceipt] = db.query(InvoiceReceipt).get(receipt_id)
    if not rec or rec.invoice_id != inv.id:
        raise HTTPException(status_code=404, detail="Чек не найден")

    # 👇 пользователь
    actor = get_actor(request, db)

    # 👇 старое состояние
    old_data = {
        "status": rec.status,
        "amount": rec.amount,
    }

    rec.status = "rejected"

    # 👇 новое состояние
    new_data = {
        "status": rec.status,
        "amount": rec.amount,
        "invoice_id": inv.id,
    }

    # 👇 аудит
    write_audit(
        db=db,
        entity_type="receipt",
        entity_id=rec.id,
        action="receipt_rejected",
        actor=actor,
        old_data=old_data,
        new_data=new_data,
        note="Чек отклонен",
    )

    db.commit()
    return RedirectResponse(url=f"/admin/invoices/{inv.id}/edit", status_code=303)

@router.post("/{invoice_id}/mark-paid")
def mark_invoice_paid(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    inv: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    # 👇 пользователь
    actor = get_actor(request, db)

    # 👇 старое состояние
    old_data = {
        "is_paid": inv.is_paid,
        "status": inv.status,
    }

    inv.is_paid = True
    inv.status = "paid"
    inv.status_changed_at = datetime.utcnow()

    # 👇 новое состояние
    new_data = {
        "is_paid": inv.is_paid,
        "status": inv.status,
        "status_changed_at": str(inv.status_changed_at),
    }

    # 👇 аудит
    write_audit(
        db=db,
        entity_type="invoice",
        entity_id=inv.id,
        action="invoice_marked_paid",
        actor=actor,
        old_data=old_data,
        new_data=new_data,
        note="Накладная отмечена как оплаченная",
    )

    db.commit()
    return RedirectResponse(url=f"/admin/invoices/{inv.id}/edit", status_code=303)