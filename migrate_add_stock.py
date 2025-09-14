# scripts/migrate_add_stock.py
import sqlite3
from app.config import BASE_DIR

db_path = (BASE_DIR / "shop.db").as_posix()
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# проверим, есть ли колонка stock у таблицы variants
cur.execute("PRAGMA table_info(variants)")
cols = [row[1] for row in cur.fetchall()]
if "stock" not in cols:
    cur.execute("ALTER TABLE variants ADD COLUMN stock INTEGER DEFAULT 0")
    print("Column 'stock' added to 'variants'")
else:
    print("Column 'stock' already exists")

conn.commit()
conn.close()
