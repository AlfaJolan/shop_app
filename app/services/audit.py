import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User

def get_actor(request: Request, db: Session) -> dict[str, Any]:
    # Берем id и роль из session, потому что именно так у тебя устроен логин
    user_id = request.session.get("user_id") if hasattr(request, "session") else None
    user_role = request.session.get("role") if hasattr(request, "session") else None

    if not user_id:
        return {
            "user_id": None,
            "username": "anonymous",
            "user_role": user_role,
        }

    # Пытаемся найти пользователя в БД, чтобы получить username
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "user_id": user_id,
            "username": f"user_{user_id}",
            "user_role": user_role,
        }

    return {
        "user_id": user.id,
        "username": user.username,
        "user_role": user.role,
    }


def write_audit(
    db: Session,
    *,
    entity_type: str,
    action: str,
    entity_id: int | None = None,
    actor: dict[str, Any] | None = None,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
    note: str | None = None,
) -> AuditLog:
    actor = actor or {
        "user_id": None,
        "username": "system",
        "user_role": None,
    }

    row = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=actor.get("user_id"),
        username=actor.get("username"),
        user_role=actor.get("user_role"),
        old_data=json.dumps(old_data, ensure_ascii=False, default=str) if old_data is not None else None,
        new_data=json.dumps(new_data, ensure_ascii=False, default=str) if new_data is not None else None,
        note=note,
    )
    db.add(row)
    return row


def write_audit(
    db: Session,
    *,
    entity_type: str,
    action: str,
    entity_id: int | None = None,
    actor: dict[str, Any] | None = None,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
    note: str | None = None,
) -> AuditLog:
    actor = actor or {
        "user_id": None,
        "username": "system",
        "user_role": None,
    }

    row = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=actor.get("user_id"),
        username=actor.get("username"),
        user_role=actor.get("user_role"),
        old_data=json.dumps(old_data, ensure_ascii=False, default=str) if old_data is not None else None,
        new_data=json.dumps(new_data, ensure_ascii=False, default=str) if new_data is not None else None,
        note=note,
    )
    db.add(row)
    return row