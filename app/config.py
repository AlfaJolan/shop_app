from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # Загружаем переменные окружения из .env

APP_NAME = "ShopApp"
ENV = os.getenv("ENV", "local")

# Строка подключения к БД
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://shop_user:testingApp@localhost:5432/shop_app"
)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
