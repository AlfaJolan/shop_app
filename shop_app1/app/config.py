from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # .env можно не создавать — возьмутся дефолты

APP_NAME = "ShopApp"
ENV = os.getenv("ENV", "local")

# SQLite-файл рядом с проектом
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///{0}".format((BASE_DIR / "shop.db").as_posix()))

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
