# app/db.py
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

# Абсолютный путь: .../Desktop/shop_app/app.db
BASE_DIR = Path(__file__).resolve().parents[1]  # папка shop_app
DB_FILE = BASE_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
