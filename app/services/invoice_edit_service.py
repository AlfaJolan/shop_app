from decimal import Decimal, InvalidOperation
from typing import Optional, List

from sqlalchemy.orm import Session, selectinload

from app.models.invoice import Invoice, InvoiceItem
from app.models.invoice_audit import InvoiceAudit
from app.models.catalog import Variant
from app.services.audit import write_audit


# ----------------------------
# 🔥 Кастомные ошибки сервиса
# ----------------------------

class InvoiceEditError(Exception):
    pass


class InvoiceValidationError(InvoiceEditError):
    pass


class InvoiceStockError(InvoiceEditError):
    pass


# ----------------------------
# 🔧 Сервис редактирования накладной
# ----------------------------

class InvoiceEditService:

    def __init__(self, db: Session):
        self.db = db

    # ----------------------------
    # 📦 Получение накладной (с загрузкой связей)
    # ----------------------------
    def get_invoice(self, invoice_id: int) -> Invoice:
        inv = (
            self.db.query(Invoice)
            .options(selectinload(Invoice.items))
            .filter(Invoice.id == invoice_id)
            .first()
        )

        if not inv:
            raise InvoiceValidationError("Накладная не найдена")

        return inv

    # ----------------------------
    # 🧠 Безопасный Decimal
    # ----------------------------
    def _dec(self, val: Optional[str], default: Decimal) -> Decimal:
        if val is None:
            return default
        val = val.replace(",", ".").strip()
        try:
            return Decimal(val)
        except (InvalidOperation, ValueError):
            return default

    # ----------------------------
    # ✏️ Обновление существующих строк (перенос твоего update)
    # ----------------------------
    def update_items(self, inv: Invoice, form, actor):
        audits: List[InvoiceAudit] = []
        changed = False

        old_items_map = {
            it.id: {
                "qty_final": int(it.qty_final),
                "unit_price_final": float(it.unit_price_final or 0),
            }
            for it in inv.items
        }

        old_total = float(getattr(inv, "total_amount_final", 0) or 0)

        changed_items_old = []
        changed_items_new = []

        for it in inv.items:
            qty_key = f"qty_final_{it.id}"
            price_key = f"unit_price_final_{it.id}"

            qty_val = form.get(qty_key)
            price_val = form.get(price_key)

            new_qty = it.qty_final
            new_price = it.unit_price_final

            # ----------------------------
            # qty
            # ----------------------------
            if qty_val is not None:
                try:
                    v = int(qty_val)
                    new_qty = max(v, 0)
                except:
                    pass

            # ----------------------------
            # price
            # ----------------------------
            if price_val is not None:
                v = self._dec(price_val, it.unit_price_final)
                new_price = max(v, Decimal("0"))

            old_stock = None
            new_stock = None

            # ----------------------------
            # изменение qty → склад
            # ----------------------------
            if int(new_qty) != int(it.qty_final):

                delta = new_qty - it.qty_final

                if not it.variant_id:
                    raise InvoiceValidationError(f"Нет variant_id у {it.product_name}")

                variant = self.db.query(Variant).get(it.variant_id)
                if not variant:
                    raise InvoiceValidationError("Вариант не найден")

                if delta > 0 and variant.stock < delta:
                    raise InvoiceStockError(
                        f"Недостаточно '{variant.name}'. Остаток {variant.stock}"
                    )

                old_stock = int(variant.stock)
                variant.stock -= delta
                new_stock = int(variant.stock)

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

            # ----------------------------
            # изменение цены
            # ----------------------------
            if Decimal(str(new_price)) != Decimal(str(it.unit_price_final or 0)):

                audits.append(InvoiceAudit(
                    invoice_id=inv.id,
                    item_id=it.id,
                    field="price",
                    old_value=Decimal(str(it.unit_price_final or 0)),
                    new_value=Decimal(str(new_price)),
                    user="admin",
                ))

                it.unit_price_final = new_price
                changed = True

            it.recompute_line()

            # ----------------------------
            # собираем diff для audit_log
            # ----------------------------
            if (
                old_items_map[it.id]["qty_final"] != it.qty_final
                or old_items_map[it.id]["unit_price_final"] != float(it.unit_price_final or 0)
            ):
                changed_items_old.append({
                    "item_id": it.id,
                    "qty": old_items_map[it.id]["qty_final"],
                })
                changed_items_new.append({
                    "item_id": it.id,
                    "qty": it.qty_final,
                    "stock": new_stock,
                })

        inv.recompute_totals()

        # ----------------------------
        # аудит
        # ----------------------------
        if changed:
            for a in audits:
                self.db.add(a)

            write_audit(
                db=self.db,
                entity_type="invoice",
                entity_id=inv.id,
                action="invoice_updated",
                actor=actor,
                old_data={"total": old_total, "items": changed_items_old},
                new_data={"total": float(inv.total_amount_final or 0), "items": changed_items_new},
                note="Обновление накладной",
            )

    # ----------------------------
    # ➕ ДОБАВЛЕНИЕ ТОВАРА (НОВОЕ)
    # ----------------------------
    def add_item(
        self,
        invoice_id: int,
        variant_id: int,
        qty: int,
        unit_price: Optional[Decimal],
        actor,
    ):

        if qty <= 0:
            raise InvoiceValidationError("Количество должно быть больше 0")

        # 🔒 блокируем накладную
        inv = (
            self.db.query(Invoice)
            .options(selectinload(Invoice.items))
            .filter(Invoice.id == invoice_id)
            .with_for_update()
            .first()
        )

        if not inv:
            raise InvoiceValidationError("Накладная не найдена")

        # 🔒 блокируем вариант
        variant = (
            self.db.query(Variant)
            .filter(Variant.id == variant_id)
            .with_for_update()
            .first()
        )

        if not variant:
            raise InvoiceValidationError("Товар не найден")

        product = variant.product

        if not product or not product.is_active:
            raise InvoiceValidationError("Товар неактивен")

        if variant.stock < qty:
            raise InvoiceStockError(
                f"Недостаточно товара. Остаток: {variant.stock}"
            )

        catalog_price = variant.unit_price or Decimal("0")
        final_price = unit_price if unit_price is not None else catalog_price

        old_total = float(inv.total_amount_final or 0)
        old_stock = int(variant.stock)

        # ----------------------------
        # 🔁 проверяем есть ли уже строка
        # ----------------------------
        existing_item = next(
            (i for i in inv.items if i.variant_id == variant.id),
            None
        )

        merged = False

        if existing_item:
            # 🔥 merge логика
            existing_item.qty_final += qty
            existing_item.recompute_line()

            variant.stock -= qty
            merged = True

        else:
            # 🆕 новая строка
            item = InvoiceItem(
                invoice_id=inv.id,
                product_id=variant.product_id,
                variant_id=variant.id,

                product_name=product.name,
                variant_name=variant.name,

                qty_original=qty,
                qty_final=qty,

                unit_price_original=catalog_price,
                unit_price_final=final_price,

                line_total_original=catalog_price * qty,
                line_total_final=final_price * qty,
            )

            self.db.add(item)

            variant.stock -= qty
            self.db.flush()  # чтобы новая строка уже существовала до recompute_totals()

        inv.recompute_totals()

        new_stock = int(variant.stock)

        # ----------------------------
        # 🧾 аудит
        # ----------------------------
        write_audit(
            db=self.db,
            entity_type="invoice",
            entity_id=inv.id,
            action="invoice_item_added",
            actor=actor,
            old_data={
                "total": old_total,
                "stock": old_stock,
            },
            new_data={
                "total": float(inv.total_amount_final or 0),
                "variant_id": variant.id,
                "qty_added": qty,
                "price": float(final_price),
                "stock": new_stock,
                "merged": merged,
            },
            note="Добавление товара в накладную",
        )

        self.db.commit()