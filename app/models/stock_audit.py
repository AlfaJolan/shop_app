# app/models/stock_audit.py
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base

class StockAudit(Base):
    __tablename__ = "stock_audit"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False, index=True)

    # INCREASE | DECREASE | SET
    change_type = Column(String(16), nullable=False)

    delta_units = Column(Integer, nullable=False)       # на сколько изменили (в штуках) или значение (для SET)
    old_stock   = Column(Integer, nullable=False)
    new_stock   = Column(Integer, nullable=False)

    boxes        = Column(Integer, nullable=True)       # сколько коробок
    units_per_box= Column(Integer, nullable=True)       # сколько в коробке
    extra_units  = Column(Integer, nullable=True)       # свободные штуки
    note         = Column(String(500), nullable=True)   # причина/комментарий

    user       = Column(String(64), nullable=False, default="admin")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    variant = relationship("Variant")
