from sqlalchemy import create_engine, text

# укажи правильный путь к своей базе
DB_PATH = "sqlite:///shop.db"   # или "sqlite:///app.db"
engine = create_engine(DB_PATH)

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, username, role, password_hash FROM users"))
    rows = result.fetchall()

    print("=== Users in DB ===")
    for row in rows:
        print(f"ID={row.id}, username={row.username}, role={row.role}, password_hash={row.password_hash}")
