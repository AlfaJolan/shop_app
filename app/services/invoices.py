from decimal import Decimal
import secrets
from sqlalchemy.orm import Session
from app.models.invoice import Invoice, InvoiceItem
from app.models.catalog import Product  # ← берём seller_id через продукт


def _make_pkey(length: int = 16) -> str:
    return secrets.token_urlsafe(length)


def create_invoice_for_order(db: Session, order, lines: list, customer_name: str, phone: str, comment: str):
    inv = Invoice(
        order_id=order.id if order else None,
        pkey=_make_pkey(16),
        is_revoked=False,
        customer_name=(customer_name or None),
        phone=(phone or None),
        comment=(comment or None),
        total_amount_final=Decimal("0.00"),
    )
    db.add(inv)
    db.flush()

    total = Decimal("0.00")
    for l in lines:
        qty = int(l["qty"])
        unit_price = Decimal(str(l["unit_price"]))
        line_total = Decimal(str(l["line_total"]))

        product_image = None
        seller_id = None
        seller_name = None
        product_id = l.get("product_id")   # 🆕 берём из order/cart line
        variant_id = l.get("variant_id")   #
        pid = l.get("product_id")
        if pid:
            p = db.query(Product).get(int(pid))
            if p:
                if p.image:
                    product_image = p.image  # например "images/milk.jpeg"
                if p.seller_id:
                    seller_id = p.seller_id
                    # если в модели Product есть relationship seller → можно взять имя
                    if hasattr(p, "seller") and p.seller:
                        seller_name = p.seller.name

        item = InvoiceItem(
            invoice_id=inv.id,
            seller_id=seller_id,          # ← сохраняем продавца
            seller_name=seller_name,      # ← и имя для истории
            product_name=l["product_name"],
            variant_name=l["variant_name"],
            product_id=product_id,        # 🆕 сохраняем product_id
            variant_id=variant_id,  
            product_image=product_image,
            qty_original=qty,
            qty_final=qty,
            unit_price_original=unit_price,
            unit_price_final=unit_price,
            line_total_original=line_total,
            line_total_final=line_total,
        )
        db.add(item)
        total += line_total

    inv.total_amount_final = total
    db.commit()
    db.refresh(inv)
    return inv
