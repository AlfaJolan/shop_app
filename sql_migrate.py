# sql_add_order_status.py
from sqlalchemy import create_engine, text

# Укажи путь к БД (проверь что файл app.db реально тут лежит)
SQLALCHEMY_DATABASE_URL = "sqlite:////Users/user/Desktop/shop_app/app.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, future=True)

def ensure_column(conn, table: str, coldef: str):
    """
    Проверяем есть ли колонка, если нет — добавляем.
    coldef = "status TEXT DEFAULT 'new'"
    """
    colname = coldef.split()[0]
    existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info('{table}')"))}
    if colname not in existing:
        print(f"Добавляю {table}.{colname} ...")
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {coldef}"))
    else:
        print(f"{table}.{colname} уже есть")

def main():
    with engine.begin() as conn:
        ensure_column(conn, "orders", "status TEXT DEFAULT 'new'")
        ensure_column(conn, "orders", "status_changed_at DATETIME")
        ensure_column(conn, "orders", "status_note TEXT")
    print("Готово.")

if __name__ == "__main__":
    main()
