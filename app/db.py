from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app import config  # импортируем настройки

Base = declarative_base()

# Создаём engine
engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency для FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
