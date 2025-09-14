from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, Query, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.order import Order
from app.models.invoice import Invoice

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])

ALLOWED_STATUSES: List[str] = ["new", "packed", "shipped", "delivered", "canceled"]
STATUS_LABELS_RU = {
    "new": "Новый",
    "packed": "Собран",
    "shipped": "Отправлен",
    "delivered": "Получен",
    "canceled": "Отменён",
}

# --------- LIVE СТРАНИЦА ----------
@router.get("/live", response_class=HTMLResponse)
def live_orders_page(request: Request):
    return templates.TemplateResponse("admin/orders_live.html", {
        "request": request,
        "allowed_statuses": ALLOWED_STATUSES,
        "status_labels": STATUS_LABELS_RU,   # <- передаём (если захотим отрисовывать по-русски и там)
        "default_status": "new",
    })

@router.get("/live-data", response_class=JSONResponse)
def live_orders(
    status: str = Query("new"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    q = db.query(Order).order_by(Order.created_at.desc())
    if status != "all":
        q = q.filter(Order.status == status)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "customer_name": r.customer_name,
            "phone": r.phone,
            "comment": r.comment,
            "total_amount": float(r.total_amount or 0),
            "status": r.status,  # в UI будем маппить на русский
        }
        for r in rows
    ]

# ---------- ДЕТАЛИ ЗАКАЗА ----------
@router.get("/{order_id}", response_class=HTMLResponse)
def order_detail(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db)
):
    order: Optional[Order] = db.query(Order).get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    invoice: Optional[Invoice] = (
        db.query(Invoice).filter(Invoice.order_id == order.id).order_by(Invoice.id.desc()).first()
    )

    return templates.TemplateResponse("admin/order_detail.html", {
        "request": request,
        "order": order,
        "invoice": invoice,
        "allowed_statuses": ALLOWED_STATUSES,
        "status_labels": STATUS_LABELS_RU,  # <- добавили
    })

# ---------- СМЕНА СТАТУСА ----------
@router.post("/{order_id}/status")
def change_status(
    order_id: int,
    new_status: str = Form(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус")

    order: Optional[Order] = db.query(Order).get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    valid_next = {
        "new": {"packed", "canceled"},
        "packed": {"shipped", "canceled"},
        "shipped": {"delivered"},
        "delivered": set(),
        "canceled": set(),
    }
    cur = order.status or "new"
    if new_status not in valid_next.get(cur, set()) and new_status != cur:
        raise HTTPException(status_code=400, detail="Недопустимый переход статуса")

    order.status = new_status
    order.status_changed_at = datetime.utcnow()
    if note:
        order.status_note = note

    db.commit()
    return RedirectResponse(url="/admin/orders/{0}".format(order.id), status_code=303)
