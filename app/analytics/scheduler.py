# app/analytics/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED  # 🆕
from pytz import timezone
from datetime import datetime
from app.telegram.telegram_notify import notifier
from app.analytics.report_builder import send_daily_report
import atexit  # 🆕
import os


_scheduler = None  # 🆕 храним глобально, чтобы планировщик не потерялся


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
        # 🆕 ошибка задачи не должна валить процесс приложения
        print(f"[AnalyticsScheduler] Ошибка при отправке отчёта: {e}")


def _scheduler_listener(event):
    """🆕 Логируем результат выполнения задач планировщика."""
    try:
        if event.exception:
            print(f"[AnalyticsScheduler] Job crashed: job_id={event.job_id}")
        else:
            print(f"[AnalyticsScheduler] Job finished: job_id={event.job_id}")
    except Exception as e:
        # 🆕 даже listener не должен ломать приложение
        print(f"[AnalyticsScheduler] Ошибка listener: {e}")


def _shutdown_scheduler():
    """🆕 Корректная остановка планировщика при завершении процесса."""
    global _scheduler
    try:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            print("[AnalyticsScheduler] Планировщик корректно остановлен.")
    except Exception as e:
        print(f"[AnalyticsScheduler] Ошибка при остановке планировщика: {e}")


def start_analytics_scheduler():
    """
    Запускает ежедневную задачу в 20:00 по времени Алматы.
    Можно добавить и другие периодические задачи по аналогии.
    """
    global _scheduler

    # ⚙️ Корректно пропускаем только процесс перезагрузчика Uvicorn/Watchfiles
    if os.environ.get("WATCHFILES_RELOADER") == "true":
        print("[AnalyticsScheduler] Пропускаем запуск в reloader-процессе.")
        return

    # 🆕 если планировщик уже был запущен, повторно не создаём
    if _scheduler and _scheduler.running:
        print("[AnalyticsScheduler] Планировщик уже запущен.")
        return

    try:
        scheduler = BackgroundScheduler(
            timezone="Asia/Almaty",
            job_defaults={
                "coalesce": True,          # 🆕 схлопываем пропущенные запуски в один
                "max_instances": 1,        # 🆕 не даём одной задаче запускаться параллельно
                "misfire_grace_time": 3600 # 🆕 даём час запаса, если процесс был занят/спал
            }
        )

        scheduler.add_listener(_scheduler_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)  # 🆕

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
        _scheduler = scheduler  # 🆕 сохраняем ссылку глобально
        atexit.register(_shutdown_scheduler)  # 🆕 корректно гасим при выходе

        print("[AnalyticsScheduler] Планировщик аналитики запущен (ежедневно в 20:00 Asia/Almaty).")
    except Exception as e:
        # 🆕 ошибка старта планировщика не должна останавливать всё приложение
        print(f"[AnalyticsScheduler] Ошибка запуска планировщика: {e}")


# 🆕 добавил отдельную остановку планировщика для app/workers/analytics_worker.py
def stop_analytics_scheduler():
    """🆕 Останавливает планировщик аналитики из worker-процесса."""
    global _scheduler

    try:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            print("[AnalyticsScheduler] Планировщик аналитики остановлен.")
    except Exception as e:
        print(f"[AnalyticsScheduler] Ошибка при остановке планировщика аналитики: {e}")