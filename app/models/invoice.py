# app/models/invoice.py
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
# app/routers/invoice.py (добавьте рядом с остальными import)
from urllib.parse import quote

def _content_disposition_utf8(pretty_filename_utf8: str, fallback_ascii: str) -> str:
    """
    Собирает Content-Disposition с ASCII-фолбэком и UTF-8 вариантом по RFC 5987.
    ВАЖНО: значение должно быть ASCII-совместимым, поэтому UTF-8 часть URL-экранируем.
    """
    return "attachment; filename=\"{fallback}\"; filename*=UTF-8''{utf8}".format(
        fallback=fallback_ascii.replace('"', ''),
        utf8=quote(pretty_filename_utf8, safe="")
    )

class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Привязка к заказу (опционально)
    #order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Публичный токен-доступ (в ссылке), можно ротировать/отзывать
    pkey: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Реквизиты клиента (копируем из заказа, чтобы не зависеть от изменений)
    customer_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    seller_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    city_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)


    # === СТАТУС ЗАКАЗА ===
    # допустимые значения: 'new' | 'packed' | 'shipped' | 'delivered' | 'cancelled'
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Итог по накладной (финал)
    total_amount_final: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    items: Mapped[List["InvoiceItem"]] = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )

    # Аудит-журнал изменений
    audits = relationship("InvoiceAudit", back_populates="invoice", cascade="all, delete-orphan")

    # Хелпер: пересчитать итог
    def recompute_totals(self):
        self.total_amount_final = sum((x.line_total_final for x in self.items), Decimal("0"))


# Состав накладной (строки)
class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))

    # привязка к продавцу (фиксируем на момент выписки накладной)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), nullable=True, index=True)
    seller_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # 🆕 привязка к продукту
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)

    # привязка к варианту
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("variants.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255))
    variant_name: Mapped[str] = mapped_column(String(120))

    # путь к картинке (относительный), например "milk.jpeg"
    product_image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    qty_original: Mapped[int] = mapped_column(Integer)
    qty_final: Mapped[int] = mapped_column(Integer)

    unit_price_original: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_price_final: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    line_total_original: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total_final: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")

    # Хелпер: пересчитать сумму строки
    def recompute_line(self):
        self.line_total_final = Decimal(str(self.unit_price_final)) * int(self.qty_final)




# Составной индекс по имени/телефону — удобно для поиска
Index("ix_invoices_customer_phone", Invoice.customer_name, Invoice.phone)
