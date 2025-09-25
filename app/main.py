from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException  # 🔹 добавили
from app.middleware.rbac import RBACMiddleware
from app.db import Base, engine
import app.models  # noqa: F401
from sqlalchemy.orm import configure_mappers
from app import config

from fastapi.templating import Jinja2Templates
from pathlib import Path
import json

# COMMIT Рабочей версий
# Рабочая версия, с RBAC и сессиями
# https://fastapi.tiangolo.com/tutorial/middleware/
configure_mappers()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ShopApp")

# RBAC проверяет роли
app.add_middleware(RBACMiddleware)

# SessionMiddleware с безопасными настройками
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    session_cookie=config.SESSION_COOKIE_NAME,
    max_age=config.SESSION_MAX_AGE,
    same_site=config.SESSION_SAMESITE,
    https_only=not config.DEBUG
)

# ==== Routers ====
from app.routers import (
    public, cart, invoice as invoice_router, admin_invoice as admin_inv_router,
    admin_dashboard, admin_orders, admin_catalog as admin_catalog_router,
    admin_products as admin_products_router, auth as auth_router,
    admin_seller as admin_sellers_router, search as search_router, admin_users, products as products_router
)
from app.telegram_subscribe import start_polling

app.include_router(public.router)
app.include_router(cart.router)
app.include_router(invoice_router.router)
app.include_router(admin_inv_router.router)
app.include_router(admin_dashboard.router)
app.include_router(admin_orders.router)
app.include_router(admin_catalog_router.router)
app.include_router(admin_products_router.router)
app.include_router(admin_sellers_router.router)
app.include_router(auth_router.router)
app.include_router(search_router.router)
app.include_router(admin_users.router)
app.include_router(products_router.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Переделать этот момент под отдельные файлы
# ==== Контакты (JSON конфиг) ====
templates = Jinja2Templates(directory="app/templates")
CONFIG_PATH = Path(__file__).parent / "config" / "contacts.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONTACTS = json.load(f)
templates.env.globals["contacts"] = CONTACTS  # теперь contacts доступны во всех шаблонах
app.state.contacts = CONTACTS                 # ← добавил

# ==== Обработчик ошибок (404) ====
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request},
            status_code=404
        )
    raise exc  # остальные ошибки пока пробрасываем

@app.get("/__routes")
def __routes():
    return [getattr(r, "path", str(r)) for r in app.routes]

@app.on_event("startup")
async def startup_event():
    print("🚀 Stop Polling")
    # start_polling()
