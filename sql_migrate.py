# scripts/migrate_clear_tables.py
import sqlite3
from app.config import BASE_DIR

db_path = (BASE_DIR / "app.db").as_posix()
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Список таблиц, которые нужно очистить
tables = ["variants", "products"]

for table in tables:
    try:
        cur.execute(f"DELETE FROM {table}")
        print(f"Таблица '{table}' очищена")
    except Exception as e:
        print(f"Ошибка при очистке {table}: {e}")


conn.commit()
conn.close()
