import requests
import time
import threading
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.telegram.config_notify import notify_settings
from app.models.subscriber import Subscriber

API_URL = f"https://api.telegram.org/bot{notify_settings.TELEGRAM_TOKEN}/"


def save_chat(chat_id: str, username: str | None):
    """Сохраняем подписчика в БД (через модель)"""
    db: Session = SessionLocal()
    try:
        exists = db.query(Subscriber).filter(Subscriber.chat_id == str(chat_id)).first()
        if not exists:
            sub = Subscriber(chat_id=str(chat_id), username=username)
            db.add(sub)
            db.commit()
    except Exception as e:
        db.rollback()
        print("Ошибка сохранения подписчика:", e)
    finally:
        db.close()


def get_updates(offset=None):
    """Получаем апдейты от Telegram"""
    url = API_URL + "getUpdates"
    params = {"timeout": 30, "offset": offset}
    return requests.get(url, params=params).json()


def polling_loop():
    #print("Polling запущен...")

    """Цикл получения сообщений от пользователей"""
    last_update_id = None
    while True:
        try:
            updates = get_updates(last_update_id).get("result", [])
            #print("Апдейты:", updates)   # 👈

            for upd in updates:
                last_update_id = upd["update_id"] + 1
                msg = upd.get("message", {})
                text = msg.get("text")
                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                username = chat.get("username")

                if text == notify_settings.TELEGRAM_ADMIN_PASSWORD:
                    save_chat(chat_id, username)
                    requests.post(API_URL + "sendMessage", data={
                        "chat_id": chat_id,
                        "text": "✅ Вы подписаны на уведомления!"
                    })
                else:
                    requests.post(API_URL + "sendMessage", data={
                        "chat_id": chat_id,
                        "text": "Введите пароль для подписки."
                    })
        except Exception as e:
            print("Ошибка polling:", e)
        time.sleep(2)


def start_polling():
    """Запускаем polling в фоне"""
    threading.Thread(target=polling_loop, daemon=True).start()
