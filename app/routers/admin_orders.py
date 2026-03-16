from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, Query, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.invoice import Invoice
from app.telegram.telegram_notify import notifier

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])

# --------- ДОПУСТИМЫЕ СТАТУСЫ ----------
ALLOWED_STATUSES: List[str] = ["new", "packed", "shipped"]

STATUS_LABELS_RU = {
    "new": "Новый",
    "packed": "Собран",
    "shipped": "Отправлен",
}

# --------- РАЗРЕШЕННЫЕ ПЕРЕХОДЫ ----------
VALID_NEXT = {
    "new": {"packed"},
    "packed": {"shipped"},
    "shipped": set(),
}


def get_available_statuses(current_status: Optional[str]) -> List[str]:
    """
    Возвращает список статусов, которые можно показать в UI для текущей накладной:
    - текущий статус
    - допустимые следующие статусы
    """
    cur = current_status or "new"
    next_set = VALID_NEXT.get(cur, set())
    return [cur] + [st for st in ALLOWED_STATUSES if st in next_set]


# --------- LIVE СТРАНИЦА ----------
@router.get("/live", response_class=HTMLResponse)
def live_orders_page(request: Request):
    return templates.TemplateResponse(
        "admin/orders_live.html",
        {
            "request": request,
            "allowed_statuses": ALLOWED_STATUSES,
            "status_labels": STATUS_LABELS_RU,
            "default_status": "new",
        },
    )


@router.get("/live-data", response_class=JSONResponse)
def live_orders(
    status: str = Query("new"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Invoice).order_by(Invoice.created_at.desc())

    if status != "all":
        q = q.filter(Invoice.status == status)

    rows = q.limit(limit).all()

    return [
        {
            "id": r.id,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "customer_name": r.customer_name,
            "phone": r.phone,
            "comment": r.comment,
            "total_amount": float(r.total_amount_final or 0),
            "status": r.status,
        }
        for r in rows
    ]


# ---------- ДЕТАЛИ ЗАКАЗА ----------
@router.get("/{invoice_id}", response_class=HTMLResponse)
def order_detail(
    request: Request,
    invoice_id: int,
    db: Session = Depends(get_db),
):
    invoice: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    available_statuses = get_available_statuses(invoice.status)

    return templates.TemplateResponse(
        "admin/order_detail.html",
        {
            "request": request,
            "invoice": invoice,
            "allowed_statuses": available_statuses,
            "status_labels": STATUS_LABELS_RU,
        },
    )


# ---------- СМЕНА СТАТУСА ----------
@router.post("/{invoice_id}/status")
def change_status(
    invoice_id: int,
    new_status: str = Form(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус")

    invoice: Optional[Invoice] = db.query(Invoice).get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    cur = invoice.status or "new"

    if new_status not in VALID_NEXT.get(cur, set()) and new_status != cur:
        raise HTTPException(status_code=400, detail="Недопустимый переход статуса")

    invoice.status = new_status
    invoice.status_changed_at = datetime.utcnow()

    if note:
        invoice.status_note = note

    db.commit()

    items = [
        {
            "name": f"{item.product_name}, {item.variant_name}",
            "qty": item.qty_final,
            "price": item.unit_price_final,
        }
        for item in invoice.items
    ]

    status_label = STATUS_LABELS_RU.get(new_status, new_status)

    notifier.notify_invoice_status_changed(
        invoice_id=invoice.id,
        new_status=status_label,
        items=items,
    )

    return RedirectResponse(url=f"/admin/orders/{invoice.id}", status_code=303)