# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.db import Base, engine

# 1) ВАЖНО: импортируем ВСЕ модели до create_all(),
#    чтобы SQLAlchemy знал про классы и связи
import app.models  # noqa: F401

# (опционально) Явная конфигурация мапперов
from sqlalchemy.orm import configure_mappers
configure_mappers()

# 2) Создаём таблицы (локалка на SQLite)
Base.metadata.create_all(bind=engine)

# 3) Подключаем роутеры ПОСЛЕ импорта моделей
from app.routers import public, admin, cart
from app.routers import invoice as invoice_router            # публичная накладная (/invoice/{id})
from app.routers import admin_invoice as admin_inv_router    # админ-редактор накладной
from app.routers import admin_dashboard                      # списки заказов/накладных/аудита
from app.routers import admin_orders                         # live-заказы/смена статуса
from app.routers import admin_catalog as admin_catalog_router  # ← НОВОЕ: CRUD категорий/каталог

app = FastAPI(title="ShopApp")

# 4) Сессии (корзина и т.п.)
app.add_middleware(SessionMiddleware, secret_key="dev-secret-change-me")

# 5) Роутеры
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(cart.router)

# Накладные (публично и админ)
app.include_router(invoice_router.router)
app.include_router(admin_inv_router.router)

# Админские панели
app.include_router(admin_dashboard.router)
app.include_router(admin_orders.router)
app.include_router(admin_catalog_router.router)  # ← подключили админ-каталог

# 6) Статика (картинки, css, шрифты)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Для отладки — вывести все пути
@app.get("/__routes")
def __routes():
    return [getattr(r, "path", str(r)) for r in app.routes]
