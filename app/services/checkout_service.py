# app/services/checkout_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.catalog import Variant
from app.models.invoice import Invoice, InvoiceReceipt
from app.services.audit import write_audit
from app.services.invoices import create_invoice
from app.utils.file_uploads import (
    FileValidationError,
    build_pdf_filename,
    save_bytes_to_path,
    validate_and_read_pdf,
    validate_files_count,
)


# 🔹 Абсолютный путь от текущего файла сервиса:
# app/services/checkout_service.py -> app -> static/uploads/receipts
BASE_DIR = Path(__file__).resolve().parents[2]
RECEIPTS_UPLOAD_ROOT = BASE_DIR / "app" / "static" / "uploads" / "receipts"


class CheckoutError(Exception):
    """Контролируемая ошибка checkout, которую можно показать пользователю."""
    pass


@dataclass
class CheckoutLineInput:
    product_id: int | None
    product_name: str
    variant_id: int
    variant_name: str
    qty: int
    unit_price: Decimal
    line_total: Decimal


@dataclass
class CheckoutInput:
    customer_name: str
    phone: str
    seller_name: str
    salesperson_id: int | None
    city_name: str
    comment: str
    lines: list[CheckoutLineInput]
    receipt_files: list[UploadFile] | None = None


@dataclass
class CheckoutResult:
    invoice_id: int
    invoice_pkey: str
    customer_name: str | None
    phone: str | None
    comment: str | None
    items: list[dict]
    has_receipts: bool


class CheckoutService:
    def __init__(self, db: Session):
        self.db = db

    async def checkout(
        self,
        data: CheckoutInput,
        *,
        actor: dict | None = None,
    ) -> CheckoutResult:
        """
        Полный атомарный checkout:
        1) lock вариантов
        2) финальная валидация остатков
        3) создание накладной
        4) списание склада
        5) аудит
        6) сохранение чеков
        7) один commit в конце
        """
        self._validate_input(data)

        saved_paths: list[Path] = []

        try:
            # 🔹 NEW: на всякий случай убираем дубли variant_id перед lock
            variant_ids = list(dict.fromkeys(int(line.variant_id) for line in data.lines))
            variants_by_id = self._lock_variants(variant_ids)

            # Финальная проверка уже ПОСЛЕ lock
            self._validate_locked_lines(data.lines, variants_by_id)

            # Преобразуем dataclass-строки в формат, который понимает текущий create_invoice(...)
            invoice_lines = [self._line_to_invoice_dict(line) for line in data.lines]

            inv = create_invoice(
                db=self.db,
                lines=invoice_lines,
                customer_name=data.customer_name,
                phone=data.phone,
                seller_name=data.seller_name,
                salesperson_id=data.salesperson_id,
                city_name=data.city_name,
                comment=data.comment,
            )

            # Списываем склад в той же транзакции
            self._decrement_stock(data.lines, variants_by_id)

            # Пишем аудит покупки в той же транзакции
            self._write_purchase_audit(
                inv=inv,
                actor=actor,
                has_receipts=bool(data.receipt_files),
            )

            # Сохраняем PDF-чек(и), если они есть
            if data.receipt_files:
                saved_paths = await self._save_receipts(inv=inv, files=data.receipt_files)

            # Один commit в самом конце
            self.db.commit()

            # После commit можно безопасно сформировать результат
            self.db.refresh(inv)

            return CheckoutResult(
                invoice_id=inv.id,
                invoice_pkey=inv.pkey,
                customer_name=inv.customer_name,
                phone=inv.phone,
                comment=inv.comment,
                items=self._build_notify_items(inv),
                has_receipts=bool(inv.receipts),
            )

        except CheckoutError:
            self.db.rollback()
            self._cleanup_saved_files(saved_paths)
            raise
        except FileValidationError as e:
            self.db.rollback()
            self._cleanup_saved_files(saved_paths)
            # 🔹 NEW: нормализуем ошибку загрузки файла в CheckoutError,
            # чтобы роут мог показать её пользователю через flash, а не уронить 500
            raise CheckoutError(str(e)) from e
        except Exception:
            self.db.rollback()
            self._cleanup_saved_files(saved_paths)
            raise

    def _validate_input(self, data: CheckoutInput) -> None:
        if not data.lines:
            raise CheckoutError("Корзина пуста.")

        for line in data.lines:
            if int(line.qty) <= 0:
                raise CheckoutError(f"Некорректное количество для позиции: {line.product_name}.")
            if int(line.variant_id) <= 0:
                raise CheckoutError(f"Некорректный variant_id для позиции: {line.product_name}.")

    def _lock_variants(self, variant_ids: list[int]) -> dict[int, Variant]:
        """
        Загружаем все нужные варианты С БЛОКИРОВКОЙ.
        Это ключевой шаг против гонок при одновременном checkout.
        """
        if not variant_ids:
            return {}

        variants = (
            self.db.query(Variant)
            # 🔹 NEW: здесь специально НЕ используем joinedload(Variant.product),
            # потому что вместе с FOR UPDATE это превращается в LEFT OUTER JOIN
            # и PostgreSQL падает с "FOR UPDATE не может применяться..."
            .filter(Variant.id.in_(variant_ids))
            .with_for_update()
            .all()
        )
        return {int(v.id): v for v in variants}

    def _validate_locked_lines(
        self,
        lines: list[CheckoutLineInput],
        variants_by_id: dict[int, Variant],
    ) -> None:
        """
        Повторная финальная проверка уже после lock.
        Здесь нельзя опираться на данные из session/cart как на истину.
        """
        unavailable: list[str] = []
        out_of_stock: list[str] = []

        for line in lines:
            v = variants_by_id.get(int(line.variant_id))
            if not v or not v.is_active or not v.product or not v.product.is_active:
                unavailable.append(line.product_name)
                continue

            if int(line.qty) > int(v.stock):
                out_of_stock.append(f"{line.product_name} ({int(v.stock)} шт.)")

        if unavailable:
            raise CheckoutError(
                "Некоторые товары больше недоступны: {0}.".format(", ".join(unavailable))
            )

        if out_of_stock:
            raise CheckoutError(
                "Недостаточно на складе по позициям: {0}.".format(", ".join(out_of_stock))
            )

    def _line_to_invoice_dict(self, line: CheckoutLineInput) -> dict:
        return {
            "product_id": line.product_id,
            "product_name": line.product_name,
            "variant_id": line.variant_id,
            "variant_name": line.variant_name,
            "qty": int(line.qty),
            "unit_price": Decimal(str(line.unit_price)),
            "line_total": Decimal(str(line.line_total)),
        }

    def _decrement_stock(
        self,
        lines: list[CheckoutLineInput],
        variants_by_id: dict[int, Variant],
    ) -> None:
        for line in lines:
            v = variants_by_id.get(int(line.variant_id))
            if not v:
                raise CheckoutError(f"Вариант не найден во время списания: {line.product_name}.")

            new_stock = int(v.stock) - int(line.qty)
            if new_stock < 0:
                raise CheckoutError(
                    f"Остаток по товару '{line.product_name}' стал отрицательным."
                )

            v.stock = new_stock

    def _write_purchase_audit(
        self,
        *,
        inv: Invoice,
        actor: dict | None,
        has_receipts: bool,
    ) -> None:
        new_data = {
            "invoice_id": inv.id,
            "customer_name": inv.customer_name,
            "phone": inv.phone,
            "seller_name": inv.seller_name,
            "salesperson_id": inv.salesperson_id,
            "city_name": inv.city_name,
            "comment": inv.comment,
            "has_receipts": has_receipts,
            "items_count": len(inv.items),
            "items": [
                {
                    "product_name": item.product_name,
                    "variant_name": item.variant_name,
                    "qty": item.qty_original,
                    "unit_price": float(item.unit_price_original)
                    if item.unit_price_original is not None else None,
                    "line_total": float(item.line_total_original)
                    if item.line_total_original is not None else None,
                }
                for item in inv.items
            ],
        }

        write_audit(
            db=self.db,
            entity_type="invoice",
            entity_id=inv.id,
            action="purchase_created",
            actor=actor,
            old_data=None,
            new_data=new_data,
            note="Оформлен новый заказ",
        )

    async def _save_receipts(
        self,
        *,
        inv: Invoice,
        files: list[UploadFile],
    ) -> list[Path]:
        """
        Сохраняем чек(и) и создаём InvoiceReceipt.
        Если в процессе что-то сломается, вызывающий код удалит уже записанные файлы.
        """
        validate_files_count(files)

        saved_paths: list[Path] = []
        invoice_dir = RECEIPTS_UPLOAD_ROOT / str(inv.id)

        for f in files:
            pdf_bytes = await validate_and_read_pdf(f)

            filename = build_pdf_filename()
            dst = invoice_dir / filename

            save_bytes_to_path(pdf_bytes, dst)
            saved_paths.append(dst)

            rec = InvoiceReceipt(
                invoice_id=inv.id,
                file_path=str(dst).replace("\\", "/"),
                uploaded_at=datetime.utcnow(),
                expired_at=datetime.utcnow() + timedelta(days=2),
                status="pending",
                amount=None,
            )
            self.db.add(rec)

        return saved_paths

    def _cleanup_saved_files(self, paths: list[Path]) -> None:
        for path in paths:
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                # Не роняем checkout повторно из-за ошибки cleanup
                pass

    def _build_notify_items(self, inv: Invoice) -> list[dict]:
        return [
            {
                "name": f"{item.product_name}, {item.variant_name}",
                "qty": item.qty_original,
                "price": item.unit_price_original,
            }
            for item in inv.items
        ]