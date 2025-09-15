import requests
from datetime import datetime
from app.telegram.config_notify import notify_settings


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send(self, message: str):
        """Отправить сообщение в Telegram"""
        try:
            requests.post(self.api_url, data={
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            })
        except Exception as e:
            print(f"Ошибка при отправке в Telegram: {e}")

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

    def notify_order_created(self, order_id, customer_name, phone, comment, items):
        """Уведомление о создании заказа"""
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = [
            f"🆕 <b>Новый заказ #{order_id}</b>",
            f"📅 {date_str}",
            f"👤 Клиент: {customer_name}",
            f"📞 Телефон: {phone or '—'}"
        ]
        if comment:
            msg.append(f"💬 Комментарий: {comment}")
        msg.append("\n📦 Состав заказа:\n" + self.format_items(items))
        self.send("\n".join(msg))

    def notify_order_status_changed(self, order_id, new_status, items):
        """Уведомление при изменении статуса"""
        msg = [
            f"⚡ <b>Заказ #{order_id}</b>",
            f"📌 Новый статус: {new_status}",
            "\n📦 Состав заказа:\n" + self.format_items(items)
        ]
        self.send("\n".join(msg))


# глобальный экземпляр
notifier = TelegramNotifier(
    token=notify_settings.TELEGRAM_TOKEN,
    chat_id=notify_settings.TELEGRAM_CHAT_ID
)
