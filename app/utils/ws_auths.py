from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.websockets import WebSocket
from app import config

async def get_user_from_ws(websocket: WebSocket):
    # Берём cookie
    raw = websocket.cookies.get(config.SESSION_COOKIE_NAME)
    if not raw:
        return None

    # Тот же объект SessionMiddleware
    sm = SessionMiddleware(app=None, secret_key=config.SECRET_KEY)
    data = sm.decode(raw)   # 👈 приватный метод, но он рабочий
    return data.get("user")
