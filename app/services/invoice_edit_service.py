# app/services/invoice_edit_service.py
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.catalog import Product, Variant
from app.models.invoice import Invoice, InvoiceItem
from app.models.invoice_audit import InvoiceAudit
from app.services.audit import write_audit


class InvoiceEditError(Exception):
    """Контролируемая ошибка бизнес-логики редактирования накладной."""


def _to_decimal(value: Any, default: str = "0.00") -> Decimal:
    """
    Безопасно приводит значение к Decimal.
    Нужен, чтобы не словить None/float-проблемы при создании строки накладной.
    """
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def search_active_invoice_variants(db: Session, q: str | None, limit: int = 20) -> list[dict[str, Any]]:
    """
    Поиск только по активным товарам и активным вариантам для добавления в накладную.

    Ищем по:
    - Product.name
    - Variant.name
    - Product.sku
    """
    limit = max(1, min(int(limit or 20), 50))
    query_text = (q or "").strip()

    query = (
        db.query(Variant, Product)
        .join(Product, Variant.product_id == Product.id)
        .filter(Product.is_active.is_(True), Variant.is_active.is_(True))
    )

    if query_text:
        like = f"%{query_text}%"
        query = query.filter(
            or_(
                Product.name.ilike(like),
                Variant.name.ilike(like),
                Product.sku.ilike(like),
            )
        )

    rows = (
        query.order_by(Product.name.asc(), Variant.name.asc(), Variant.id.asc())
        .limit(limit)
        .all()
    )

    results: list[dict[str, Any]] = []
    for variant, product in rows:
        seller = product.seller if product else None

        results.append({
            "product_id": product.id if product else None,
            "variant_id": variant.id,
            "product_name": product.name if product else "—",
            "variant_name": variant.name,
            "sku": product.sku if product and product.sku else None,
            "stock": int(variant.stock or 0),
            "unit_price": float(variant.unit_price) if variant.unit_price is not None else None,
            "product_image": product.image if product else None,
            "seller_name": seller.name if seller else None,
        })

    return results


def add_variant_to_invoice(
    db: Session,
    *,
    invoice_id: int,
    variant_id: int,
    qty: int,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Добавляет товар в накладную.

    Правила:
    - доступны только активные Product + Variant
    - если variant_id уже есть в накладной -> merge в существующую строку
    - merge меняет только final-часть (qty_final / line_total_final)
    - original-поля существующей строки не трогаем
    - склад уменьшается в той же транзакции
    - Variant блокируется через FOR UPDATE для Postgres
    """
    if qty is None or int(qty) <= 0:
        raise InvoiceEditError("Количество должно быть больше 0.")

    qty = int(qty)

    inv = db.query(Invoice).get(invoice_id)
    if not inv:
        raise InvoiceEditError("Накладная не найдена.")

    # 🔒 Лочим только Variant без joinedload, чтобы Postgres не падал на FOR UPDATE + OUTER JOIN
    variant = (
        db.query(Variant)
        .filter(Variant.id == variant_id)
        .with_for_update()
        .first()
    )
    if not variant:
        raise InvoiceEditError("Вариант товара не найден.")

    product = db.query(Product).get(variant.product_id)
    if not product:
        raise InvoiceEditError("Товар для выбранного варианта не найден.")

    if not product.is_active:
        raise InvoiceEditError("Нельзя добавить неактивный товар в накладную.")

    if not variant.is_active:
        raise InvoiceEditError("Нельзя добавить неактивный вариант в накладную.")

    if variant.stock < qty:
        raise InvoiceEditError(
            f"Недостаточно товара '{variant.name}'. На складе {variant.stock}, требуется {qty}."
        )

    # Цена продажи обязательна для накладной
    unit_price = variant.unit_price
    if unit_price is None:
        raise InvoiceEditError("У выбранного варианта не заполнена цена продажи.")

    unit_price_dec = _to_decimal(unit_price, "0.00")
    net_cost_dec = _to_decimal(variant.unit_price_net_cost, "0.00")

    old_invoice_total = float(getattr(inv, "total_amount_final", 0) or 0)
    stock_before = int(variant.stock or 0)

    existing_item = (
        db.query(InvoiceItem)
        .filter(
            InvoiceItem.invoice_id == inv.id,
            InvoiceItem.variant_id == variant.id,
        )
        .first()
    )

    # ===== MERGE В СУЩЕСТВУЮЩУЮ СТРОКУ =====
    if existing_item:
        qty_before = int(existing_item.qty_final)
        line_total_before = float(existing_item.line_total_final or 0)

        new_qty = qty_before + qty

        existing_item.qty_final = new_qty
        existing_item.recompute_line()

        variant.stock -= qty
        stock_after = int(variant.stock or 0)

        inv.recompute_totals()

        # Детальный аудит изменения количества существующей строки
        db.add(InvoiceAudit(
            invoice_id=inv.id,
            item_id=existing_item.id,
            field="qty",
            old_value=Decimal(str(qty_before)),
            new_value=Decimal(str(new_qty)),
            user=(actor or {}).get("username") or "admin",
        ))

        write_audit(
            db=db,
            entity_type="invoice",
            entity_id=inv.id,
            action="invoice_item_merged",
            actor=actor,
            old_data={
                "invoice_id": inv.id,
                "total_amount_final": old_invoice_total,
                "item": {
                    "item_id": existing_item.id,
                    "product_id": existing_item.product_id,
                    "variant_id": existing_item.variant_id,
                    "product_name": existing_item.product_name,
                    "variant_name": existing_item.variant_name,
                    "qty_before": qty_before,
                    "line_total_before": line_total_before,
                    "variant_stock_before": stock_before,
                },
            },
            new_data={
                "invoice_id": inv.id,
                "total_amount_final": float(getattr(inv, "total_amount_final", 0) or 0),
                "item": {
                    "item_id": existing_item.id,
                    "product_id": existing_item.product_id,
                    "variant_id": existing_item.variant_id,
                    "product_name": existing_item.product_name,
                    "variant_name": existing_item.variant_name,
                    "qty_added": qty,
                    "qty_after": int(existing_item.qty_final),
                    "unit_price_final": float(existing_item.unit_price_final) if existing_item.unit_price_final is not None else None,
                    "line_total_after": float(existing_item.line_total_final or 0),
                    "variant_stock_after": stock_after,
                },
            },
            note="Добавление товара в накладную с merge по существующей позиции",
        )

        db.commit()

        return {
            "mode": "merged",
            "invoice_id": inv.id,
            "item_id": existing_item.id,
            "variant_id": variant.id,
            "qty_added": qty,
            "qty_after": int(existing_item.qty_final),
            "variant_stock_after": stock_after,
            "invoice_total_after": float(getattr(inv, "total_amount_final", 0) or 0),
        }

    # ===== СОЗДАНИЕ НОВОЙ СТРОКИ =====
    product_image = product.image if product.image else None
    seller = product.seller

    line_total = unit_price_dec * qty

    new_item = InvoiceItem(
        invoice_id=inv.id,
        seller_id=product.seller_id,
        seller_name=seller.name if seller else None,
        product_id=product.id,
        variant_id=variant.id,
        product_name=product.name,
        variant_name=variant.name,
        product_image=product_image,
        qty_original=qty,
        qty_final=qty,
        unit_price_net_cost=net_cost_dec,
        unit_price_original=unit_price_dec,
        unit_price_final=unit_price_dec,
        line_total_original=line_total,
        line_total_final=line_total,
    )

    db.add(new_item)

    variant.stock -= qty
    stock_after = int(variant.stock or 0)

    # flush нужен, чтобы получить new_item.id до общего аудита
    db.flush()

    inv.recompute_totals()

    write_audit(
        db=db,
        entity_type="invoice",
        entity_id=inv.id,
        action="invoice_item_added",
        actor=actor,
        old_data={
            "invoice_id": inv.id,
            "total_amount_final": old_invoice_total,
        },
        new_data={
            "invoice_id": inv.id,
            "total_amount_final": float(getattr(inv, "total_amount_final", 0) or 0),
            "added_item": {
                "item_id": new_item.id,
                "product_id": new_item.product_id,
                "variant_id": new_item.variant_id,
                "product_name": new_item.product_name,
                "variant_name": new_item.variant_name,
                "qty_original": int(new_item.qty_original),
                "qty_final": int(new_item.qty_final),
                "unit_price_net_cost": float(new_item.unit_price_net_cost) if new_item.unit_price_net_cost is not None else None,
                "unit_price_original": float(new_item.unit_price_original) if new_item.unit_price_original is not None else None,
                "unit_price_final": float(new_item.unit_price_final) if new_item.unit_price_final is not None else None,
                "line_total_original": float(new_item.line_total_original) if new_item.line_total_original is not None else None,
                "line_total_final": float(new_item.line_total_final) if new_item.line_total_final is not None else None,
                "variant_stock_before": stock_before,
                "variant_stock_after": stock_after,
            },
        },
        note="Добавление новой позиции в накладную",
    )

    db.commit()

    return {
        "mode": "created",
        "invoice_id": inv.id,
        "item_id": new_item.id,
        "variant_id": variant.id,
        "qty_added": qty,
        "qty_after": int(new_item.qty_final),
        "variant_stock_after": stock_after,
        "invoice_total_after": float(getattr(inv, "total_amount_final", 0) or 0),
    }