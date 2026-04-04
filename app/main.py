from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException  # 🔹 добавили
from app.middleware.rbac import RBACMiddleware
from app.db import Base, engine
import app.models  # noqa: F401
from sqlalchemy.orm import configure_mappers
from app import config
from apscheduler.schedulers.background import BackgroundScheduler
from app.tasks.cleanup_receipts import cleanup_old_receipts
from app.analytics.scheduler import start_analytics_scheduler

from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.routers import admin_audit
from app.routers.admin_product_import import router as admin_product_import_router

import json
import time
import logging
import os  # 🆕 для защиты от повторного запуска в reloader-процессе

# COMMIR рабочей версий
# COMMIT Рабочей версий
# Рабочая версия, с RBAC и сессиями
# https://fastapi.tiangolo.com/tutorial/middleware/
configure_mappers()

app = FastAPI(title="ShopApp")

# 🔹 Логгер приложения
logger = logging.getLogger("shop_app")

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
    admin_seller as admin_sellers_router, search as search_router, admin_users, products as products_router, ws_orders as ws_orders_router,
    admin_salespersons as salespersons_router
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
app.include_router(admin_audit.router) # ✅ добавляем роуты аудита
app.include_router(products_router.router)
app.include_router(ws_orders_router.router)
app.include_router(salespersons_router.router)
app.include_router(admin_product_import_router) # ✅ добавляем роуты импорта продуктов первая версия, без аудита и без телеграма

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Переделать этот момент под отдельные файлы
# ==== Контакты (JSON конфиг) ====
templates = Jinja2Templates(directory="app/templates")
CONFIG_PATH = Path(__file__).parent / "config" / "contacts.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONTACTS = json.load(f)
templates.env.globals["contacts"] = CONTACTS  # теперь contacts доступны во всех шаблонах
app.state.contacts = CONTACTS                 # ← добавил

templates.env.globals["build_ts"] = str(int(time.time()))

# 🔹 Один экземпляр scheduler, но запускаем его только на startup
scheduler = BackgroundScheduler()

# 🔹 Флаги, чтобы не было повторного запуска тяжёлых задач
app.state.scheduler_started = False
app.state.analytics_started = False

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

# 🔹 Логирование времени запросов — помогает искать медленные endpoint'ы
@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    logger.info("%s %s -> %s in %.3fs", request.method, request.url.path, response.status_code, duration)
    return response


@app.on_event("startup")
async def on_startup():
    """Запуск планировщика при старте приложения"""

    # 🔹 Создание таблиц переносим на startup, чтобы не делать это при импорте модуля
    try:
        Base.metadata.create_all(bind=engine)
        print("[App] Таблицы проверены.")
    except Exception as e:
        print("[App] Ошибка при create_all:", e)

    # 🆕 не запускаем фоновые задачи в reloader-процессе
    is_reloader = os.environ.get("WATCHFILES_RELOADER") == "true"
    if is_reloader:
        print("[App] Пропускаем startup фоновых задач в reloader-процессе.")
        print("🚀 Stop Polling")
        # start_polling()
        return

    # 🔹 Запускаем cleanup scheduler только один раз
    if not app.state.scheduler_started:
        try:
            scheduler.add_job(
                cleanup_old_receipts,
                "interval",
                hours=24,
                id="cleanup_old_receipts",
                replace_existing=True
            )  # раз в сутки
            scheduler.start()
            app.state.scheduler_started = True
            print("[App] Cleanup scheduler запущен.")
        except Exception as e:
            print("[App] Ошибка запуска cleanup scheduler:", e)

    # 🔹 Аналитический scheduler запускаем только один раз
    if not app.state.analytics_started:
        try:
            start_analytics_scheduler()
            app.state.analytics_started = True
            print("[App] Планировщик запущен.")
        except Exception as e:
            print("[App] Ошибка запуска analytics scheduler:", e)

    # 🔹 Тестовую отправку отключаем в проде, чтобы не тормозить startup
    if config.DEBUG:
        try:
            # generate_analytics_report()
            print("[App] DEBUG режим: тестовая отправка аналитики отключена.")
        except Exception as e:
            print("[App] Ошибка при тестовой отправке:", e)

    print("🚀 Stop Polling")
    # start_polling()


@app.on_event("shutdown")
def shutdown_event():
    # 🔹 Аккуратно выключаем scheduler только если он был запущен
    if app.state.scheduler_started:
        try:
            scheduler.shutdown(wait=False)  # 🆕 не блокируем остановку приложения
            print("[App] Cleanup scheduler остановлен.")
        except Exception as e:
            print("[App] Ошибка при остановке cleanup scheduler:", e)