from datetime import datetime, timedelta
import math

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])
templates = Jinja2Templates(directory="app/templates")


# ---- DB ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_class=HTMLResponse)
def audit_index(
    request: Request,
    username: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: int | None = Query(None),
    date_from: str | None = Query(None),   # формат YYYY-MM-DD
    date_to: str | None = Query(None),     # формат YYYY-MM-DD
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)

    # ---- filters ----
    if username:
        query = query.filter(AuditLog.username == username)

    if action:
        query = query.filter(AuditLog.action == action)

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)

    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(AuditLog.created_at >= dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            # включаем весь день до 23:59:59
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(AuditLog.created_at < dt_to)
        except ValueError:
            pass

    # ---- total ----
    total = query.count()

    # ---- pagination ----
    pages = max(1, math.ceil(total / per_page))
    if page > pages:
        page = pages

    logs = (
        query.order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # ---- filter options for UI ----
    usernames = [
        row[0]
        for row in db.query(AuditLog.username)
        .filter(AuditLog.username.isnot(None))
        .distinct()
        .order_by(AuditLog.username.asc())
        .all()
    ]

    actions = [
        row[0]
        for row in db.query(AuditLog.action)
        .filter(AuditLog.action.isnot(None))
        .distinct()
        .order_by(AuditLog.action.asc())
        .all()
    ]

    entity_types = [
        row[0]
        for row in db.query(AuditLog.entity_type)
        .filter(AuditLog.entity_type.isnot(None))
        .distinct()
        .order_by(AuditLog.entity_type.asc())
        .all()
    ]

    return templates.TemplateResponse(
        "admin/audit.html",
        {
            "request": request,
            "logs": logs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,

            # текущие фильтры
            "username": username,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "date_from": date_from,
            "date_to": date_to,

            # опции для select
            "usernames": usernames,
            "actions": actions,
            "entity_types": entity_types,
        },
    )