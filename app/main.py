from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from app.db import Base, engine

# 1) Импортируем все модели до create_all(),
#    чтобы SQLAlchemy знал про классы и связи
import app.models  # noqa: F401

from sqlalchemy.orm import configure_mappers
configure_mappers()

# 2) Создаём таблицы
Base.metadata.create_all(bind=engine)


# ==== Middleware ====
class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # проверяем только /admin (кроме /login)
        if request.url.path.startswith("/admin") and not request.url.path.startswith("/login"):
            if not request.session.get("is_admin"):
                return RedirectResponse("/login")
        return await call_next(request)


# ==== FastAPI app ====
app = FastAPI(title="ShopApp")

app.add_middleware(AdminAuthMiddleware)

# Сессии (корзина и т.п.)
app.add_middleware(SessionMiddleware, secret_key="dev-secret-change-me")
# Проверка админ-доступа


# ==== Routers ====
from app.routers import public, cart
from app.routers import invoice as invoice_router
from app.routers import admin_invoice as admin_inv_router
from app.routers import admin_dashboard
from app.routers import admin_orders
from app.routers import admin_catalog as admin_catalog_router
from app.routers import admin_products as admin_products_router
from app.routers import auth as auth_router
from app.routers import admin_seller as admin_sellers_router
from app.telegram_subscribe import start_polling
from app.routers import search as search_router
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

# ==== Static ====
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ==== Debug route ====
@app.get("/__routes")
def __routes():
    return [getattr(r, "path", str(r)) for r in app.routes]

@app.on_event("startup")
async def startup_event():
    print("🚀 Запуск приложения, стартуем polling")
    start_polling()