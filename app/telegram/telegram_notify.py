import requests
from datetime import datetime
from app.telegram.config_notify import notify_settings
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.subscriber import Subscriber
from app import config  # импортируем настройки

class TelegramNotifier:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
    

    def send(self, message: str):
        """Отправить сообщение всем подписчикам в Telegram"""
        db: Session = SessionLocal()
        try:
            subscribers = db.query(Subscriber).all()
            for sub in subscribers:
                try:
                    requests.post(self.api_url, data={
                        'chat_id': sub.chat_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    })
                except Exception as e:
                    print(f"Ошибка при отправке {sub.chat_id}: {e}")
        except Exception as e:
            print("Ошибка при выборке подписчиков:", e)
        finally:
            db.close()

    def format_items(self, items):
        """Форматирование списка товаров"""
        lines = []
        total_sum = 0
        for item in items:
            subtotal = item["qty"] * item["price"]
            total_sum += subtotal
            lines.append(f"• {item['name']} × {item['qty']} шт. = {subtotal} ₸")
        lines.append(f"\n💰 Итого: {total_sum} ₸")
        return "\n".join(lines)

    def notify_invoice_created(self, invoice_id,invoice_pkey, customer_name, phone, comment, items):
        """Уведомление о создании накладной (бывший заказ)"""
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = [
            f"🆕 <b>Новый заказ #{invoice_id}</b>",   # 🔹 заменили заказ → накладная
            f"📅 {date_str}",
            f"👤 Клиент: {customer_name}",
            f"📞 Телефон: {phone or '—'}"
        ]
        if comment:
            msg.append(f"💬 Комментарий: {comment}")
            
        invoice_url = f"{config.BASE_URL}/invoice/{invoice_id}?pkey={invoice_pkey}"
        msg.append(f"🔗 <a href='{invoice_url}'>Открыть накладную</a>")        
        msg.append("\n📦 Состав заказа:\n" + self.format_items(items))
        self.send("\n".join(msg))

    def notify_invoice_status_changed(self, invoice_id, new_status, items):
        """Уведомление при изменении статуса накладной"""
        msg = [
            f"⚡ <b>Заказ #{invoice_id}</b>",   # 🔹 заменили заказ → накладная
            f"📌 Новый статус: {new_status}",
            "\n📦 Состав заказа:\n" + self.format_items(items)
        ]
        self.send("\n".join(msg))


# глобальный экземпляр
notifier = TelegramNotifier(
    token=notify_settings.TELEGRAM_TOKEN
)
