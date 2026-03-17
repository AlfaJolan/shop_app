import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def get_actor(request: Request) -> dict[str, Any]:
    user = request.session.get("user") if hasattr(request, "session") else None

    if not user:
        return {
            "user_id": None,
            "username": "anonymous",
            "user_role": None,
        }

    if isinstance(user, dict):
        return {
            "user_id": user.get("id"),
            "username": (
                user.get("username")
                or user.get("login")
                or user.get("name")
                or (f"user_{user.get('id')}" if user.get("id") is not None else "unknown")
            ),
            "user_role": user.get("role"),
        }

    if isinstance(user, str):
        return {
            "user_id": None,
            "username": user,
            "user_role": None,
        }

    return {
        "user_id": None,
        "username": "unknown",
        "user_role": None,
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