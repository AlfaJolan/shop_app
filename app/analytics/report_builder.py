# app/analytics/report_builder.py
from datetime import datetime, timedelta
from app.db import SessionLocal
from app.analytics import queries
from app.telegram.telegram_notify import notifier
from pytz import timezone


def _fmt_kzt(value):
    """Форматирование чисел в стиле: 1 234 567 ₸"""
    return f"{int(value):,}".replace(",", " ") + " ₸"


def _fmt_percent(value):
    """Форматирует изменение: +5.3% или -2.1%"""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def _growth(today, yesterday):
    """Вычисляет % рост относительно вчера."""
    if yesterday == 0:
        return 0
    return round(((today - yesterday) / yesterday) * 100, 1)


# ============================================================
# 🧾 ГЛАВНАЯ ФУНКЦИЯ: СБОР ЕЖЕДНЕВНОГО ОТЧЁТА
# ============================================================

def build_daily_report():
    """Собирает текст ежедневной аналитики за сегодня."""

    db = SessionLocal()
    try:
        now = datetime.now(timezone("Asia/Almaty"))
        today = now.date()
        yesterday = today - timedelta(days=1)

        # --- Основные метрики ---
        summary_today = queries.get_summary(
            db,
            datetime.combine(today, datetime.min.time()),
            datetime.combine(today + timedelta(days=1), datetime.min.time())
        )
        summary_yesterday = queries.get_summary(
            db,
            datetime.combine(yesterday, datetime.min.time()),
            datetime.combine(today, datetime.min.time())
        )

        revenue_growth = _growth(summary_today["revenue"], summary_yesterday["revenue"])
        qty_growth = _growth(summary_today["qty"], summary_yesterday["qty"])
        margin_growth = _growth(summary_today["margin"], summary_yesterday["margin"])

        # --- Топы ---
        top_sellers = queries.get_top_sellers(db, datetime.combine(today, datetime.min.time()),
                                              datetime.combine(today + timedelta(days=1), datetime.min.time()))
        bad_sellers = queries.get_top_sellers(db, datetime.combine(today, datetime.min.time()),
                                              datetime.combine(today + timedelta(days=1), datetime.min.time()), asc=True)

        top_products = queries.get_top_products(db, datetime.combine(today, datetime.min.time()),
                                                datetime.combine(today + timedelta(days=1), datetime.min.time()))
        bad_products = queries.get_top_products(db, datetime.combine(today, datetime.min.time()),
                                                datetime.combine(today + timedelta(days=1), datetime.min.time()), asc=True)

        # --- Города ---
        city_sellers = queries.get_cities(db, datetime.combine(today, datetime.min.time()),
                                          datetime.combine(today + timedelta(days=1), datetime.min.time()), by="sellers")
        city_orders = queries.get_cities(db, datetime.combine(today, datetime.min.time()),
                                         datetime.combine(today + timedelta(days=1), datetime.min.time()), by="orders")

        # --- 7 и 30 дней ---
        summary_7 = queries.get_summary(db, *(queries._period_days(7)))
        summary_30 = queries.get_summary(db, *(queries._period_days(30)))

        # =======================================================
        # Формируем сообщение
        # =======================================================
        msg = []
        msg.append(f"📊 <b>Ежедневная аналитика — {today.strftime('%d.%m.%Y')}</b>\n")

        msg.append(
            f"💰 Выручка: {_fmt_kzt(summary_today['revenue'])} ({_fmt_percent(revenue_growth)} к вчера)\n"
            f"📦 Кол-во: {summary_today['qty']} ({_fmt_percent(qty_growth)} к вчера)\n"
            f"🏦 Маржа: {_fmt_kzt(summary_today['margin'])} ({_fmt_percent(margin_growth)} к вчера)\n"
        )

        # --- Топ продавцов ---
        msg.append("\n👨‍💼 <b>Топ-10 продавцов</b>:\n")
        for i, s in enumerate(top_sellers, start=1):
            msg.append(f"{i}. {s['name']} — {_fmt_kzt(s['revenue'])} ({int(s['qty'])} шт, маржа {_fmt_kzt(s['margin'])})")
        msg.append("\n📉 <b>Антитоп-10 продавцов</b>:\n")
        for i, s in enumerate(bad_sellers, start=1):
            msg.append(f"{i}. {s['name']} — {_fmt_kzt(s['revenue'])} ({int(s['qty'])} шт)")

        # --- Топ товаров ---
        msg.append("\n🏷️ <b>Топ-10 товаров</b>:\n")
        for i, p in enumerate(top_products, start=1):
            msg.append(f"{i}. {p['name']} — {_fmt_kzt(p['revenue'])} ({int(p['qty'])} шт, маржа {_fmt_kzt(p['margin'])})")
        msg.append("\n📉 <b>Антитоп-10 товаров</b>:\n")
        for i, p in enumerate(bad_products, start=1):
            msg.append(f"{i}. {p['name']} — {_fmt_kzt(p['revenue'])} ({int(p['qty'])} шт)")

        # --- Города ---
        msg.append("\n🌍 <b>Продажи по городам (продавцы)</b>:\n")
        for c in city_sellers:
            msg.append(f"{c['city']} — {_fmt_kzt(c['revenue'])}")
        msg.append("\n🏙️ <b>Продажи по городам (заказы)</b>:\n")
        for c in city_orders:
            msg.append(f"{c['city']} — {_fmt_kzt(c['revenue'])}")

        # --- Периоды ---
        msg.append("\n📅 <b>Итоги за 7 дней</b>:\n"
                   f"Выручка: {_fmt_kzt(summary_7['revenue'])}\n"
                   f"Кол-во: {summary_7['qty']}\n"
                   f"Маржа: {_fmt_kzt(summary_7['margin'])}\n")

        msg.append("\n📅 <b>Итоги за 30 дней</b>:\n"
                   f"Выручка: {_fmt_kzt(summary_30['revenue'])}\n"
                   f"Кол-во: {summary_30['qty']}\n"
                   f"Маржа: {_fmt_kzt(summary_30['margin'])}\n")

        return "\n".join(msg)

    finally:
        db.close()


# ============================================================
# 🚀 ОТПРАВКА В TELEGRAM
# ============================================================

def send_daily_report():
    """Формирует и отправляет ежедневный отчёт в Telegram (чат аналитики)."""
    try:
        message = build_daily_report()
        notifier.send_analytics(message)
        print("[AnalyticsReport] Отчёт отправлен в Telegram.")
    except Exception as e:
        print("[AnalyticsReport] Ошибка при отправке отчёта:", e)
