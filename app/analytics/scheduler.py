# app/analytics/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from datetime import datetime
from app.telegram.telegram_notify import notifier
from app.analytics.report_builder import send_daily_report


def generate_analytics_report():
    """
    Основная функция — сюда позже добавим сбор аналитики.
    Сейчас просто тестовое уведомление.
    """
    now = datetime.now(timezone("Asia/Almaty"))
    message = (
        f"📊 <b>Ежедневная аналитика</b>\n"
        f"🕗 Время формирования: {now:%Y-%m-%d %H:%M}\n\n"
        f"✅ Планировщик работает корректно.\n"
        f"Далее сюда будет отправляться полный отчёт по продажам."
    )

    def generate_analytics_report():
        """Основная функция планировщика."""
        send_daily_report()
    print(f"[AnalyticsScheduler] Сообщение отправлено в {now.strftime('%H:%M')}.")


def start_analytics_scheduler():
    """
    Запускает ежедневную задачу в 20:00 по времени Алматы.
    Можно добавить и другие периодические задачи по аналогии.
    """
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
