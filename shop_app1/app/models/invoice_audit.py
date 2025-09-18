from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.db import Base

class InvoiceAudit(Base):
    __tablename__ = "invoice_audit"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("invoice_items.id"), nullable=True)

    # какое поле меняли: "qty" или "price"
    field = Column(String(32), nullable=False)  # 'qty' | 'price'
    old_value = Column(Numeric(12, 2))
    new_value = Column(Numeric(12, 2))

    user = Column(String(64), nullable=False, default="admin")  # пока без авторизации
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    invoice = relationship("Invoice", back_populates="audits")
