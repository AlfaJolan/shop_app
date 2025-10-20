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
    
    # 🔹 Базовый метод отправки сообщений по типу чата
    def _send_to_type(self, message: str, chat_type: str = "sales"):
        """Отправить сообщение только подписчикам определённого типа"""
        print(f"[DEBUG] _send_to_type() вызван для chat_type={chat_type}")

        db: Session = SessionLocal()
        try:
            subscribers = db.query(Subscriber).filter(Subscriber.chat_type == chat_type).all()
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

    # 🔹 Отправка в разные категории чатов
    def send_sales(self, message: str):
        """Отправить сообщение только в чаты продаж"""
        self._send_to_type(message, "sales")

    def send_analytics(self, message: str):
        """Отправить сообщение только в чаты аналитики"""
        self._send_to_type(message, "analytics")

    def send_admins(self, message: str):
        """Отправить сообщение только в административные чаты"""
        self._send_to_type(message, "analytics")

    # ============================================================
    # 🔹 ДОПОЛНЕНО: Отправка фото-графиков в чат аналитики
    # ============================================================
    def send_photo_analytics(self, image_bytes):
        """Отправка графика в чат аналитики (PNG как фото)"""
        db: Session = SessionLocal()
        try:
            analytics_chats = db.query(Subscriber).filter(Subscriber.chat_type == "analytics").all()
            for sub in analytics_chats:
                try:
                    files = {
                        'photo': ('analytics.png', image_bytes, 'image/png')
                    }
                    requests.post(
                        f"https://api.telegram.org/bot{self.token}/sendPhoto",
                        data={'chat_id': sub.chat_id},
                        files=files
                    )
                except Exception as e:
                    print(f"Ошибка при отправке графика {sub.chat_id}: {e}")
        except Exception as e:
            print("Ошибка при выборке чатов аналитики:", e)
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

    def notify_invoice_created(self, invoice_id, invoice_pkey, customer_name, phone, comment, items):
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
        self.send_sales("\n".join(msg))  # ✅ теперь идёт в чат продаж

    def notify_invoice_status_changed(self, invoice_id, new_status, items):
        """Уведомление при изменении статуса накладной"""
        msg = [
            f"⚡ <b>Заказ #{invoice_id}</b>",   # 🔹 заменили заказ → накладная
            f"📌 Новый статус: {new_status}",
            "\n📦 Состав заказа:\n" + self.format_items(items)
        ]
        self.send_sales("\n".join(msg))  # ✅ теперь идёт в чат продаж

    def notify_receipt_uploaded(self, invoice_id, customer_name):
        """Уведомление о загрузке нового чека"""
        msg = [
            f"🧾 Новый чек к накладной #{invoice_id}",
            f"👤 Клиент: {customer_name or '—'}",
        ]
        self.send_sales("\n".join(msg))

    def notify_receipt_status_changed(self, invoice_id, receipt_id, status, amount=None):
        """Уведомление при изменении статуса чека"""
        msg = [
            f"📑 Чек #{receipt_id} по накладной #{invoice_id}",
            f"⚡ Статус: {status}",
        ]
        if amount:
            msg.append(f"💰 Сумма: {amount:.2f} ₸")
        self.send_sales("\n".join(msg))


# глобальный экземпляр
notifier = TelegramNotifier(
    token=notify_settings.TELEGRAM_TOKEN
)
