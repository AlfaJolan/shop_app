from pathlib import Path
from dotenv import load_dotenv
import os

# === Базовые настройки ===
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # Загружаем переменные окружения из .env

APP_NAME = "SellerApp"
ENV = os.getenv("ENV", "local")  # local / prod / staging

# === База данных ===
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://shop_user:testingApp@localhost:5432/shop_app"
)

# === Безопасность ===
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

# DEBUG-флаг: True для локалки, False для продакшена
DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

# === Настройки сессий ===
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "shop_session")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", 60 * 60 * 24 * 7))  # по умолчанию 7 дней
SESSION_SAMESITE = os.getenv("SESSION_SAMESITE", "lax")  # lax / strict / none
SESSION_SECURE = os.getenv("SESSION_SECURE", str(not DEBUG)).lower() in ("1", "true", "yes")
SESSION_HTTPONLY = os.getenv("SESSION_HTTPONLY", "true").lower() in ("1", "true", "yes")

# === Redis для server-side сессий (опционально) ===
REDIS_URL = os.getenv("REDIS_URL")  # например: redis://localhost:6379/0

#BASE_URL = "http://127.0.0.1:8000"  # локально
BASE_URL = "https://economzhasa.kz"  # на проде

# === Прочее (можно расширять) ===
# Например, email-конфиг, API-ключи и т.д.
