from datetime import datetime
from typing import Optional, List, Dict, Set
from fastapi import APIRouter, Request, Depends, Query, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from itsdangerous import URLSafeSerializer
from starlette.requests import Request

from app.db import get_db
from app.models.invoice import Invoice
from app.telegram.telegram_notify import notifier
from app import config

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin/orders/status", tags=["admin-orders"])

# --------- ДОПУСТИМЫЕ СТАТУСЫ ----------
ALLOWED_STATUSES: List[str] = ["new", "paid", "packed", "shipped"]

STATUS_LABELS_RU = {
    "new": "Новый",
    "paid": "Оплачен",
    "packed": "Собран",
    "shipped": "Отправлен",
}

ALLOWED_ROLES = {"admin", "seller", "picker"}
active_connections: set[WebSocket] = set()


def get_status_counts(db: Session) -> Dict[str, int]:
    counts = {s: 0 for s in ALLOWED_STATUSES}
    for s in counts:
        counts[s] = db.query(Invoice).filter(Invoice.status == s).count()
    return counts


@router.websocket("/ws/orders")
async def ws_orders(websocket: WebSocket, db: Session = Depends(get_db)):
    # достаём сессию напрямую из scope
    session = websocket.scope.get("session", {})

    role = session.get("role")
    username = session.get("username") or f"user{session.get('user_id')}"

    if not role or role not in ALLOWED_ROLES:
        print("🚫 Нет доступа:", role)
        await websocket.close(code=1008)
        return

    await websocket.accept()
    print(f"🔌 Connected: {username} ({role})")
    active_connections.add(websocket)

    try:
        counts = get_status_counts(db)
        await websocket.send_json({"type": "status_counts", "counts": counts})

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"❌ Disconnected: {username} ({role})")
