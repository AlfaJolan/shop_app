from fastapi.templating import Jinja2Templates
from pathlib import Path
import json

templates = Jinja2Templates(directory="app/templates")

# загрузка contacts.json
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "contacts.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONTACTS = json.load(f)

templates.env.globals["contacts"] = CONTACTS
