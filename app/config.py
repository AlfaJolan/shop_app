from pathlib import Path
from dotenv import load_dotenv
import os

# === Базовые настройки ===
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # Загружаем переменные окружения из .env

# === Основные параметры приложения ===
APP_NAME = os.getenv("APP_NAME", "SellerApp")
ENV = os.getenv("ENV", "local")  # local / prod / staging
DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

# === База данных ===
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set in .env")

# === Безопасность ===
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
if ENV == "prod" and SECRET_KEY == "dev-secret-change-me":
    raise RuntimeError("SECRET_KEY must be changed for production")

# === Настройки сессий ===
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "shop_session")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", 60 * 60 * 24 * 7))  # 7 дней
SESSION_SAMESITE = os.getenv("SESSION_SAMESITE", "lax")  # lax / strict / none
SESSION_SECURE = os.getenv("SESSION_SECURE", str(not DEBUG)).lower() in ("1", "true", "yes")
SESSION_HTTPONLY = os.getenv("SESSION_HTTPONLY", "true").lower() in ("1", "true", "yes")

# === Redis (опционально) ===
REDIS_URL = os.getenv("REDIS_URL")

# === URL сайта ===
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

# === Telegram (опционально) ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ADMIN_PASSWORD = os.getenv("TELEGRAM_ADMIN_PASSWORD")
TELEGRAM_ANALYTICS_CHAT_ID = os.getenv("TELEGRAM_ANALYTICS_CHAT_ID")

# === Планировщик аналитики ===
ANALYTICS_CRON_HOUR = int(os.getenv("ANALYTICS_CRON_HOUR", 20))
ANALYTICS_CRON_MINUTE = int(os.getenv("ANALYTICS_CRON_MINUTE", 0))
ANALYTICS_TIMEZONE = os.getenv("ANALYTICS_TIMEZONE", "Asia/Almaty")
