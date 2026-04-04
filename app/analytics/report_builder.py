# app/analytics/report_builder.py
from datetime import datetime, timedelta
from app.db import SessionLocal
from app.analytics import queries
from app.analytics import plots  # ✅ добавлено для построения графиков
from app.telegram.telegram_notify import notifier
from pytz import timezone
import numpy as np  # 🆕 для heatmap матрицы
import traceback


ALMATY_TZ = timezone("Asia/Almaty")  # 🆕 чтобы не создавать timezone каждый раз


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

def build_daily_report(db=None):
    """Собирает текст ежедневной аналитики за сегодня."""

    own_db = db is None
    if own_db:
        db = SessionLocal()

    try:
        now = datetime.now(ALMATY_TZ)
        today = now.date()
        yesterday = today - timedelta(days=1)

        today_start = datetime.combine(today, datetime.min.time())  # 🆕
        tomorrow_start = datetime.combine(today + timedelta(days=1), datetime.min.time())  # 🆕
        yesterday_start = datetime.combine(yesterday, datetime.min.time())  # 🆕

        period_7 = queries._period_days(7)   # 🆕
        period_30 = queries._period_days(30)  # 🆕

        # --- Основные метрики ---
        summary_today = queries.get_summary(
            db,
            today_start,
            tomorrow_start
        )
        summary_yesterday = queries.get_summary(
            db,
            yesterday_start,
            today_start
        )

        revenue_growth = _growth(summary_today["revenue"], summary_yesterday["revenue"])
        qty_growth = _growth(summary_today["qty"], summary_yesterday["qty"])
        margin_growth = _growth(summary_today["margin"], summary_yesterday["margin"])

        # --- Топы ---
        top_sellers = queries.get_top_sellers(db, today_start, tomorrow_start)
        bad_sellers = queries.get_top_sellers(db, today_start, tomorrow_start, asc=True)

        top_products = queries.get_top_products(db, today_start, tomorrow_start)
        bad_products = queries.get_top_products(db, today_start, tomorrow_start, asc=True)

        # 🆕 Топы по торговцам
        top_salespersons = queries.get_top_salespersons(db, today_start, tomorrow_start)
        bad_salespersons = queries.get_top_salespersons(db, today_start, tomorrow_start, asc=True)

        # --- Города ---
        city_sellers = queries.get_cities(db, today_start, tomorrow_start, by="sellers")
        city_orders = queries.get_cities(db, today_start, tomorrow_start, by="orders")

        # --- 7 и 30 дней ---
        summary_7 = queries.get_summary(db, *period_7)
        summary_30 = queries.get_summary(db, *period_30)

        # 🆕 Доп. метрики (AOV, корзина, % маржи)
        aov_7 = queries.get_avg_order_value(db, *period_7)             # 🆕
        aov_30 = queries.get_avg_order_value(db, *period_30)           # 🆕
        basket_7 = queries.get_avg_basket_size(db, *period_7)          # 🆕
        basket_30 = queries.get_avg_basket_size(db, *period_30)        # 🆕
        margin_pct_7 = (summary_7["margin"] / summary_7["revenue"] * 100) if summary_7["revenue"] else 0.0  # 🆕
        margin_pct_30 = (summary_30["margin"] / summary_30["revenue"] * 100) if summary_30["revenue"] else 0.0  # 🆕

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

        # 🆕 --- Топ торговцев ---
        msg.append("\n🧑‍💼 <b>Топ-10 торговцев</b>:\n")
        for i, sp in enumerate(top_salespersons, start=1):
            msg.append(f"{i}. {sp['name']} — {_fmt_kzt(sp['revenue'])} ({int(sp['qty'])} шт, маржа {_fmt_kzt(sp['margin'])})")
        msg.append("\n📉 <b>Антитоп-10 торговцев</b>:\n")
        for i, sp in enumerate(bad_salespersons, start=1):
            msg.append(f"{i}. {sp['name']} — {_fmt_kzt(sp['revenue'])} ({int(sp['qty'])} шт)")

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
                   f"Маржа: {_fmt_kzt(summary_7['margin'])} ({margin_pct_7:.1f}%)\n"  # 🆕
                   f"🧾 AOV: {_fmt_kzt(aov_7)} | Корзина: {basket_7:.2f} шт/заказ\n"   # 🆕
                   )

        msg.append("\n📅 <b>Итоги за 30 дней</b>:\n"
                   f"Выручка: {_fmt_kzt(summary_30['revenue'])}\n"
                   f"Кол-во: {summary_30['qty']}\n"
                   f"Маржа: {_fmt_kzt(summary_30['margin'])} ({margin_pct_30:.1f}%)\n"  # 🆕
                   f"🧾 AOV: {_fmt_kzt(aov_30)} | Корзина: {basket_30:.2f} шт/заказ\n"   # 🆕
                   )
        # --- KPI по торговцам ---
        msg.append("\n👨‍💼 <b>KPI по торговцам (30 дней)</b>:\n")
        kpi_salespersons = queries.get_salesperson_kpi(db, *period_30)
        if kpi_salespersons:
            for s in kpi_salespersons:
                msg.append(
                    f"{s['name']} — {_fmt_kzt(s['revenue'])}, "
                    f"AOV {_fmt_kzt(s['avg_order_value'])}, "
                    f"Маржа {_fmt_kzt(s['margin'])}, "
                    f"Отмены {s['cancel_rate']:.1f}%"
                )
        else:
            msg.append("_Нет данных по торговцам за период._")

        return "\n".join(msg)

    finally:
        if own_db:
            db.close()


# ============================================================
# 🚀 ОТПРАВКА В TELEGRAM
# ============================================================

def send_daily_report():
    """Формирует и отправляет ежедневный отчёт в Telegram (чат аналитики)."""
    db = SessionLocal()
    try:
        period_7 = queries._period_days(7)    # 🆕
        period_30 = queries._period_days(30)  # 🆕

        message = build_daily_report(db=db)

        # --- Получаем данные для графиков (7 дней) ---
        data7 = queries.get_daily_dynamics(db, days=7)
        top_sellers_7 = queries.get_top_sellers(db, *period_7)
        top_products_7 = queries.get_top_products(db, *period_7)
        top_salespersons_7 = queries.get_top_salespersons(db, *period_7)  # 🆕
        cities_7 = queries.get_cities(db, *period_7)

        # --- Получаем данные для графиков (30 дней) ---
        data30 = queries.get_daily_dynamics(db, days=30)
        top_sellers_30 = queries.get_top_sellers(db, *period_30)
        top_products_30 = queries.get_top_products(db, *period_30)
        top_salespersons_30 = queries.get_top_salespersons(db, *period_30)  # 🆕
        cities_30 = queries.get_cities(db, *period_30)

        # 🆕 Доп. данные: категории и heatmap
        top_categories_30 = queries.get_top_categories(db, *period_30)  # 🆕
        heat_rows = queries.get_hourly_heatmap(db, *period_30)          # 🆕

        # --- Строим графики за 7 дней ---
        img_dynamics_7 = plots.plot_sales_dynamics(data7, "7")
        img_top_sellers_7 = plots.plot_bar_top(top_sellers_7, "Топ продавцов за 7 дней")
        img_top_products_7 = plots.plot_bar_top(top_products_7, "Топ товаров за 7 дней")
        img_top_salespersons_7 = plots.plot_bar_top(top_salespersons_7, "Топ торговцев за 7 дней")  # 🆕
        img_city_7 = plots.plot_city_pie(cities_7, "Продажи по городам (7 дней)")

        # --- Строим графики за 30 дней ---
        img_dynamics_30 = plots.plot_sales_dynamics(data30, "30")
        img_top_sellers_30 = plots.plot_bar_top(top_sellers_30, "Топ продавцов за 30 дней")
        img_top_products_30 = plots.plot_bar_top(top_products_30, "Топ товаров за 30 дней")
        img_top_salespersons_30 = plots.plot_bar_top(top_salespersons_30, "Топ торговцев за 30 дней")  # 🆕
        img_city_30 = plots.plot_city_pie(cities_30, "Продажи по городам (30 дней)")

        # 🆕 Новые графики: топ категорий (30д) и тепловая карта (30д)
        img_top_categories_30 = plots.plot_top_categories(top_categories_30, "Топ категорий (30 дней)")  # 🆕
        # подготовка матрицы heatmap 7x24
        matrix = np.zeros((7, 24), dtype=float)  # 🆕
        for r in heat_rows:
            dow, hour, rev = int(r["dow"]), int(r["hour"]), float(r["revenue"])
            if 0 <= dow < 7 and 0 <= hour < 24:
                matrix[dow, hour] = rev
        img_heatmap_30 = plots.plot_heatmap_demand(matrix, "Активность заказов по дням/часам (30 дней)")  # 🆕

        # 🆕 Тепловая карта за 7 дней
        heat_rows_7 = queries.get_hourly_heatmap(db, *period_7)  # 🆕
        matrix_7 = np.zeros((7, 24), dtype=float)  # 🆕
        for r in heat_rows_7:
            dow, hour, rev = int(r["dow"]), int(r["hour"]), float(r["revenue"])
            if 0 <= dow < 7 and 0 <= hour < 24:
                matrix_7[dow, hour] = rev
        img_heatmap_7 = plots.plot_heatmap_demand(matrix_7, "Активность заказов по дням/часам (7 дней)")  # 🆕
        # 🆕 добавлена тепловая карта за 7 дней

        # Добавлена отправка новых метрик для продавцев 
        # --- Отправляем текстовый отчёт ---
        notifier.send_analytics(message)
        # графики
        kpi_salespersons = queries.get_salesperson_kpi(db, *period_30)
        img_salesperson_kpi = plots.plot_salesperson_kpi_bars(kpi_salespersons)
        # --- Отправляем графики ---
        images = [
            img_dynamics_7, img_top_sellers_7, img_top_products_7, img_top_salespersons_7, img_city_7,
            img_dynamics_30, img_top_sellers_30, img_top_products_30, img_top_salespersons_30, img_city_30,
            img_top_categories_30, img_heatmap_30, img_heatmap_7, img_salesperson_kpi  # 🆕 добавлены новые
        ]

        images = [img for img in images if img]  # 🆕 убираем пустые значения заранее

        # 🆕 отправка пачками быстрее, чем по одной картинке
        notifier.send_photo_analytics_batch(images, batch_size=10)

        print("[AnalyticsReport] Отчёт и графики (7 и 30 дней) отправлены в Telegram.")
    except Exception as e:
        print("[AnalyticsReport] Ошибка при отправке отчёта:", e)
        traceback.print_exc()

    finally:
        db.close()