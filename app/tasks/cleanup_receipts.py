import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.invoice import InvoiceReceipt

def cleanup_old_receipts():
    """Удаляем файлы чеков старше 2 дней, в БД отмечаем expired_at."""
    db: Session = SessionLocal()
    try:
        threshold = datetime.utcnow() - timedelta(days=2)
        receipts = db.query(InvoiceReceipt).filter(InvoiceReceipt.uploaded_at < threshold).all()

        removed = 0
        for r in receipts:
            if r.file_path and os.path.exists(r.file_path):
                try:
                    os.remove(r.file_path)
                    print(f"🗑 Удалён файл: {r.file_path}")
                    removed += 1
                except Exception as e:
                    print(f"⚠️ Ошибка удаления {r.file_path}: {e}")
            # помечаем как expired
            r.status = "expired"
            r.expired_at = datetime.utcnow()

        db.commit()
        print(f"✅ Очистка завершена. Удалено файлов: {removed}")
    finally:
        db.close()
