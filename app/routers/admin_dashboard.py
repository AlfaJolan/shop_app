# app/routers/admin_dashboard.py
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.db import get_db
from app.models.order import Order
from app.models.invoice import Invoice
from app.models.invoice_audit import InvoiceAudit

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin", tags=["admin-dashboard"])


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


@router.get("/orders", response_class=HTMLResponse)
def list_orders(
    request: Request,
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="поиск по имени/телефону"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    query = db.query(Order).order_by(Order.created_at.desc())

    if q:
        like = "%%%s%%" % q
        query = query.filter(or_(Order.customer_name.ilike(like), Order.phone.ilike(like)))

    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    if df and dt:
        dt_end = datetime(dt.year, dt.month, dt.day, 23, 59, 59)
        query = query.filter(and_(Order.created_at >= df, Order.created_at <= dt_end))
    elif df:
        query = query.filter(Order.created_at >= df)
    elif dt:
        dt_end = datetime(dt.year, dt.month, dt.day, 23, 59, 59)
        query = query.filter(Order.created_at <= dt_end)

    orders = query.all()
    return templates.TemplateResponse("admin/orders_list.html", {
        "request": request,
        "orders": orders,
        "q": q or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
    })


@router.get("/invoices", response_class=HTMLResponse)
def list_invoices(
    request: Request,
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="поиск по имени/телефону/комментарию"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    query = db.query(Invoice).order_by(Invoice.created_at.desc())

    if q:
        like = "%%%s%%" % q
        query = query.filter(
            or_(
                Invoice.customer_name.ilike(like),
                Invoice.phone.ilike(like),
                Invoice.comment.ilike(like),
            )
        )

    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    if df and dt:
        dt_end = datetime(dt.year, dt.month, dt.day, 23, 59, 59)
        query = query.filter(and_(Invoice.created_at >= df, Invoice.created_at <= dt_end))
    elif df:
        query = query.filter(Invoice.created_at >= df)
    elif dt:
        dt_end = datetime(dt.year, dt.month, dt.day, 23, 59, 59)
        query = query.filter(Invoice.created_at <= dt_end)

    invoices = query.all()
    return templates.TemplateResponse("admin/invoices_list.html", {
        "request": request,
        "invoices": invoices,
        "q": q or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
    })


@router.get("/audit", response_class=HTMLResponse)
def list_audit(
    request: Request,
    db: Session = Depends(get_db),
    invoice_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="поиск по полю/пользователю"),
    limit: int = Query(200, ge=1, le=2000),
):
    # ВАЖНО: было InvoiceAudit.changed_at — такого поля нет. Используем created_at.
    query = db.query(InvoiceAudit).order_by(InvoiceAudit.created_at.desc())

    if invoice_id:
        query = query.filter(InvoiceAudit.invoice_id == invoice_id)
    if q:
        like = "%%%s%%" % q
        query = query.filter(or_(InvoiceAudit.field.ilike(like), InvoiceAudit.user.ilike(like)))

    entries = query.limit(limit).all()

    return templates.TemplateResponse("admin/audit_list.html", {
        "request": request,
        "entries": entries,
        "invoice_id": invoice_id,
        "q": q or "",
        "limit": limit,
    })
