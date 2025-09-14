# check_tables.py (в корне shop_app)
import sqlite3, os
from app.db import DB_FILE

print("Using DB:", DB_FILE, "exists:", os.path.exists(DB_FILE))
con = sqlite3.connect(str(DB_FILE))
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in cur.fetchall()])
con.close()
