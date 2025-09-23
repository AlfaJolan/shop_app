import json
import pathlib

CONFIG_PATH = pathlib.Path(__file__).parent / "contacts.json"

def load_contacts():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# при первом импорте сразу загрузим
CONTACTS = load_contacts()
