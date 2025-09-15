from sqlalchemy import Column, Integer, String, DateTime, func
from app.db import Base


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
