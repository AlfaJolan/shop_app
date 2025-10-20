# app/analytics/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from datetime import datetime
from app.telegram.telegram_notify import notifier
from app.analytics.report_builder import send_daily_report
import os


def generate_analytics_report1():
    """
    Основная функция — сюда позже добавим сбор аналитики.
    Сейчас просто тестовое уведомление.
    """
    print("[DEBUG] generate_analytics_report() вызван")

    now = datetime.now(timezone("Asia/Almaty"))
    message = (
        f"📊 <b>Ежедневная аналитика</b>\n"
        f"🕗 Время формирования: {now:%Y-%m-%d %H:%M}\n\n"
        f"✅ Планировщик работает корректно.\n"
        f"Далее сюда будет отправляться полный отчёт по продажам."
    )

    # 🔹 Отправляем тестовое сообщение в Telegram
    try:
        notifier.send_analytics(message)
        print(f"[AnalyticsScheduler] Сообщение отправлено в {now.strftime('%H:%M')}.")
    except Exception as e:
        print(f"[AnalyticsScheduler] Ошибка при отправке: {e}")

def generate_analytics_report():
    """
    Основная функция планировщика.
    Собирает и отправляет реальный отчёт.
    """
    print("[DEBUG] generate_analytics_report() вызван")

    try:
        send_daily_report()  # ✅ теперь будет реальный отчёт
        now = datetime.now(timezone("Asia/Almaty"))
        print(f"[AnalyticsScheduler] Отчёт аналитики отправлен в {now.strftime('%H:%M')}.")
    except Exception as e:
        print(f"[AnalyticsScheduler] Ошибка при отправке отчёта: {e}")

def start_analytics_scheduler():
    """
    Запускает ежедневную задачу в 20:00 по времени Алматы.
    Можно добавить и другие периодические задачи по аналогии.
    """
    # ⚙️ Проверяем, что это не процесс uvicorn reloader
    if os.getenv("RUN_MAIN") != "true":
        print("[AnalyticsScheduler] Пропускаем запуск в reloader-процессе.")
        return

    scheduler = BackgroundScheduler(timezone="Asia/Almaty")

    # Ежедневно в 20:00
    scheduler.add_job(
        generate_analytics_report,
        trigger="cron",
        hour=20,
        minute=0,
        id="daily_analytics_report",
        replace_existing=True
    )

    scheduler.start()
    print("[AnalyticsScheduler] Планировщик аналитики запущен (ежедневно в 20:00 Asia/Almaty).")
