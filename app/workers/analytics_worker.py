from __future__ import annotations

import atexit
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

from app.analytics.scheduler import start_analytics_scheduler, stop_analytics_scheduler, generate_analytics_report  # 🆕 добавил generate_analytics_report для тестовой отправки при старте
from app.tasks.cleanup_receipts import cleanup_old_receipts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shop_app.analytics_worker")

cleanup_scheduler = BackgroundScheduler(
    timezone=timezone("Asia/Almaty"),
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 3600,
    },
)


def start_worker():
    logger.info("[AnalyticsWorker] Starting background jobs...")

    try:
        cleanup_scheduler.add_job(
            cleanup_old_receipts,
            trigger="interval",
            hours=24,
            id="cleanup_old_receipts",
            replace_existing=True,
        )
        cleanup_scheduler.start()
        logger.info("[AnalyticsWorker] Cleanup scheduler started.")
    except Exception as e:
        logger.exception("[AnalyticsWorker] Failed to start cleanup scheduler: %s", e)

    try:
        start_analytics_scheduler()
        logger.info("[AnalyticsWorker] Analytics scheduler started.")

        generate_analytics_report()  # 🆕 тестовая отправка аналитики при старте worker; чтобы отключить, просто закомментируй эту строку
        logger.info("[AnalyticsWorker] Test analytics report sent on startup.")
    except Exception as e:
        logger.exception("[AnalyticsWorker] Failed to start analytics scheduler: %s", e)

    atexit.register(stop_worker)

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        stop_worker()


def stop_worker():
    try:
        stop_analytics_scheduler()
    except Exception as e:
        logger.exception("[AnalyticsWorker] Failed to stop analytics scheduler: %s", e)

    try:
        if cleanup_scheduler.running:
            cleanup_scheduler.shutdown(wait=False)
            logger.info("[AnalyticsWorker] Cleanup scheduler stopped.")
    except Exception as e:
        logger.exception("[AnalyticsWorker] Failed to stop cleanup scheduler: %s", e)


if __name__ == "__main__":
    start_worker()