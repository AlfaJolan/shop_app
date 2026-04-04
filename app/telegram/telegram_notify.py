import json
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
        self.photo_url = f"https://api.telegram.org/bot{self.token}/sendPhoto"  # 🆕
        self.media_group_url = f"https://api.telegram.org/bot{self.token}/sendMediaGroup"  # 🆕
        self.session = requests.Session()  # 🆕 переиспользуем одно соединение

    def _get_chat_ids(self, chat_type: str | None = None):
        """Получить chat_id подписчиков"""
        db: Session = SessionLocal()
        try:
            query = db.query(Subscriber)
            if chat_type:
                query = query.filter(Subscriber.chat_type == chat_type)
            subscribers = query.all()
            return [sub.chat_id for sub in subscribers]
        except Exception as e:
            if chat_type:
                print(f"Ошибка при выборке подписчиков типа {chat_type}:", e)
            else:
                print("Ошибка при выборке подписчиков:", e)
            return []
        finally:
            db.close()

    def _post_message(self, chat_id, message: str):
        """Отправить одно сообщение в Telegram"""
        self.session.post(
            self.api_url,
            data={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            },
            timeout=20
        )

    # 🔹 Базовый метод отправки сообщений по типу чата
    def _send_to_type(self, message: str, chat_type: str = "sales"):
        """Отправить сообщение только подписчикам определённого типа"""
        print(f"[DEBUG] _send_to_type() вызван для chat_type={chat_type}")

        chat_ids = self._get_chat_ids(chat_type)
        for chat_id in chat_ids:
            try:
                self._post_message(chat_id, message)
            except Exception as e:
                print(f"Ошибка при отправке {chat_id}: {e}")

    def send(self, message: str):
        """Отправить сообщение всем подписчикам в Telegram"""
        chat_ids = self._get_chat_ids()
        for chat_id in chat_ids:
            try:
                self._post_message(chat_id, message)
            except Exception as e:
                print(f"Ошибка при отправке {chat_id}: {e}")

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
        analytics_chat_ids = self._get_chat_ids("analytics")
        for chat_id in analytics_chat_ids:
            try:
                image_bytes.seek(0)  # 🆕 на случай повторной отправки одного и того же буфера
                files = {
                    'photo': ('analytics.png', image_bytes, 'image/png')
                }
                self.session.post(
                    self.photo_url,
                    data={'chat_id': chat_id},
                    files=files,
                    timeout=120
                )
            except Exception as e:
                print(f"Ошибка при отправке графика {chat_id}: {e}")

    # 🆕 Быстрая отправка нескольких графиков пачками
    def send_photo_analytics_batch(self, images, batch_size: int = 10):
        """Отправка нескольких графиков в чат аналитики пачками"""
        analytics_chat_ids = self._get_chat_ids("analytics")
        if not analytics_chat_ids or not images:
            return

        valid_images = [img for img in images if img]
        if not valid_images:
            return

        for chat_id in analytics_chat_ids:
            for i in range(0, len(valid_images), batch_size):
                batch = valid_images[i:i + batch_size]

                files = {}
                media = []

                try:
                    for idx, image_bytes in enumerate(batch):
                        file_key = f"photo{idx}"
                        image_bytes.seek(0)  # 🆕 обязательно перед отправкой
                        files[file_key] = ('analytics.png', image_bytes, 'image/png')
                        media.append({
                            "type": "photo",
                            "media": f"attach://{file_key}",
                        })

                    self.session.post(
                        self.media_group_url,
                        data={
                            'chat_id': chat_id,
                            'media': json.dumps(media)
                        },
                        files=files,
                        timeout=180
                    )
                except Exception as e:
                    print(f"Ошибка при пакетной отправке графиков {chat_id}: {e}")

                    # 🆕 fallback: если media group не сработал — отправим по одной
                    for image_bytes in batch:
                        try:
                            image_bytes.seek(0)
                            files = {
                                'photo': ('analytics.png', image_bytes, 'image/png')
                            }
                            self.session.post(
                                self.photo_url,
                                data={'chat_id': chat_id},
                                files=files,
                                timeout=120
                            )
                        except Exception as inner_e:
                            print(f"Ошибка при fallback-отправке графика {chat_id}: {inner_e}")

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