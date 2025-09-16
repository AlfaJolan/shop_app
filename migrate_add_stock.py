# scripts/migrate_add_user.py
import sqlite3
from app.config import BASE_DIR
from app.utils.security import hash_password

db_path = (BASE_DIR / "app.db").as_posix()
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# создаём таблицу users, если нет
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    role TEXT
)
""")

# проверим, есть ли пользователь admin
cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
exists = cur.fetchone()

if not exists:
    password_hash = hash_password("123456")
    cur.execute(
        "INSERT INTO users (username, password_hash, is_admin, role) VALUES (?, ?, ?, ?)",
        ("admin", password_hash, 1, "admin"),
    )
    print("✅ Admin user created (username='admin', password='123456')")
else:
    print("ℹ️ Admin user already exists")

conn.commit()
conn.close()
