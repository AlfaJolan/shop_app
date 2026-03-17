from datetime import datetime, timedelta
import math
import json

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
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


def parse_json_field(value):
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def pretty_json(value) -> str:
    if value is None:
        return "{}"
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def get_action_meta(action: str) -> dict:
    action = action or ""

    if "create" in action or action in {"purchase_created", "user_created", "seller_created", "salesperson_created", "product_created"}:
        return {
            "label": "Создание",
            "icon": "fa-solid fa-plus",
            "group": "success",
        }

    if "update" in action or action in {"user_updated", "seller_updated", "product_updated", "invoice_updated"}:
        return {
            "label": "Обновление",
            "icon": "fa-solid fa-pen",
            "group": "primary",
        }

    if "delete" in action or action in {"seller_deleted", "salesperson_deleted"}:
        return {
            "label": "Удаление",
            "icon": "fa-solid fa-trash",
            "group": "danger",
        }

    if "approved" in action or action in {"invoice_marked_paid", "status_change"}:
        return {
            "label": "Подтверждение / статус",
            "icon": "fa-solid fa-circle-check",
            "group": "warning",
        }

    if "rejected" in action:
        return {
            "label": "Отклонение",
            "icon": "fa-solid fa-ban",
            "group": "danger",
        }

    if "reset" in action:
        return {
            "label": "Сброс",
            "icon": "fa-solid fa-rotate-left",
            "group": "purple",
        }

    return {
        "label": "Действие",
        "icon": "fa-solid fa-clock-rotate-left",
        "group": "secondary",
    }


@router.get("/", response_class=HTMLResponse)
def audit_index(
    request: Request,
    username: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
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

    # ---- enrich logs for UI ----
    for log in logs:
        log.old_data_parsed = parse_json_field(log.old_data)
        log.new_data_parsed = parse_json_field(log.new_data)
        log.old_data_pretty = pretty_json(log.old_data_parsed)
        log.new_data_pretty = pretty_json(log.new_data_parsed)
        log.action_meta = get_action_meta(log.action)

    # ---- group by day ----
    grouped_logs = []
    current_day = None
    current_logs = []

    for log in logs:
        day_key = log.created_at.strftime("%d.%m.%Y") if log.created_at else "Без даты"

        if current_day != day_key:
            if current_logs:
                grouped_logs.append({
                    "day": current_day,
                    "logs": current_logs,
                })
            current_day = day_key
            current_logs = [log]
        else:
            current_logs.append(log)

    if current_logs:
        grouped_logs.append({
            "day": current_day,
            "logs": current_logs,
        })

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
            "grouped_logs": grouped_logs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "username": username,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "date_from": date_from,
            "date_to": date_to,
            "usernames": usernames,
            "actions": actions,
            "entity_types": entity_types,
        },
    )