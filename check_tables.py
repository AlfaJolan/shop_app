# scripts/migrate_add_seller_to_orders.py
import sqlite3
from app.config import BASE_DIR

db_path = (BASE_DIR / "app.db").as_posix()
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Проверим колонки
cur.execute("PRAGMA table_info(orders)")
cols = [row[1] for row in cur.fetchall()]

if "seller_name" not in cols:
    cur.execute("ALTER TABLE orders ADD COLUMN seller_name TEXT")
    print("✅ Колонка seller_name добавлена")

if "city_name" not in cols:
    cur.execute("ALTER TABLE orders ADD COLUMN city_name TEXT")
    print("✅ Колонка city_name добавлена")

conn.commit()
conn.close()
