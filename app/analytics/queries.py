# app/analytics/queries.py
from sqlalchemy import text
from datetime import datetime, timedelta

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _period_days(days: int):
    """Возвращает пару (start_date, end_date) для последних N дней."""
    today = datetime.utcnow().date()
    start = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())
    return start_dt, end_dt


# ============================================================
# ОСНОВНЫЕ ЗАПРОСЫ
# ============================================================

def get_summary(db, start_date, end_date):
    """Основные итоги (qty, revenue, margin) за период."""
    q = text("""
        SELECT
            COALESCE(SUM(ii.qty_final), 0) AS qty,
            COALESCE(SUM(ii.line_total_final), 0) AS revenue,
            COALESCE(SUM((ii.unit_price_final - ii.unit_price_net_cost) * ii.qty_final), 0) AS margin
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled';
    """)
    return dict(db.execute(q, {"start_date": start_date, "end_date": end_date}).mappings().first())


# ============================================================
# ТОП / АНТиТОП ПРОДАВЦОВ
# ============================================================

def get_top_sellers(db, start_date, end_date, limit=10, asc=False):
    """Топ или антитоп продавцов (по revenue, потом qty)."""
    order = "ASC" if asc else "DESC"
    q = text(f"""
        SELECT
            COALESCE(ii.seller_name, s.name) AS name,
            SUM(ii.qty_final) AS qty,
            SUM(ii.line_total_final) AS revenue,
            SUM((ii.unit_price_final - ii.unit_price_net_cost) * ii.qty_final) AS margin
        FROM invoice_items ii
        LEFT JOIN sellers s ON s.id = ii.seller_id
        JOIN invoices inv ON inv.id = ii.invoice_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled'
        GROUP BY COALESCE(ii.seller_name, s.name)
        ORDER BY revenue {order}, qty {order}
        LIMIT :limit;
    """)
    return [dict(r) for r in db.execute(q, {"start_date": start_date, "end_date": end_date, "limit": limit}).mappings().all()]


# ============================================================
# 🆕 ТОП / АНТиТОП ТОРГОВЦЕВ
# ============================================================

def get_top_salespersons(db, start_date, end_date, limit=10, asc=False):
    """Топ или антитоп торговцев (по revenue, потом qty)."""
    order = "ASC" if asc else "DESC"
    q = text(f"""
        SELECT
            COALESCE(sp.name, 'Без продавца') AS name,
            SUM(ii.qty_final) AS qty,
            SUM(ii.line_total_final) AS revenue,
            SUM((ii.unit_price_final - ii.unit_price_net_cost) * ii.qty_final) AS margin
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        LEFT JOIN salespersons sp ON sp.id = inv.salesperson_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled'
        GROUP BY COALESCE(sp.name, 'Без продавца')
        ORDER BY revenue {order}, qty {order}
        LIMIT :limit;
    """)
    return [
        dict(r)
        for r in db.execute(
            q, {"start_date": start_date, "end_date": end_date, "limit": limit}
        ).mappings().all()
    ]



# ============================================================
# ТОП / АНТиТОП ТОВАРОВ
# ============================================================

def get_top_products(db, start_date, end_date, limit=10, asc=False):
    """Топ или антитоп товаров (по revenue, потом qty)."""
    order = "ASC" if asc else "DESC"
    q = text(f"""
        SELECT
            ii.product_name AS name,
            SUM(ii.qty_final) AS qty,
            SUM(ii.line_total_final) AS revenue,
            SUM((ii.unit_price_final - ii.unit_price_net_cost) * ii.qty_final) AS margin
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled'
        GROUP BY ii.product_name
        ORDER BY revenue {order}, qty {order}
        LIMIT :limit;
    """)
    return [dict(r) for r in db.execute(q, {"start_date": start_date, "end_date": end_date, "limit": limit}).mappings().all()]


# ============================================================
# ПРОДАЖИ ПО ГОРОДАМ
# ============================================================

def get_cities(db, start_date, end_date, by="sellers"):
    """
    Возвращает продажи по городам.
    by = "sellers"  → берём sellers.city
    by = "orders"   → берём invoices.city_name
    """
    if by == "sellers":
        city_expr = "COALESCE(s.city, '—')"
    else:
        city_expr = "COALESCE(inv.city_name, '—')"

    q = text(f"""
        SELECT
            {city_expr} AS city,
            SUM(ii.qty_final) AS qty,
            SUM(ii.line_total_final) AS revenue,
            SUM((ii.unit_price_final - ii.unit_price_net_cost) * ii.qty_final) AS margin
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        LEFT JOIN sellers s ON s.id = ii.seller_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled'
        GROUP BY {city_expr}
        ORDER BY revenue DESC
        LIMIT 5;
    """)
    return [dict(r) for r in db.execute(q, {"start_date": start_date, "end_date": end_date}).mappings().all()]


# ============================================================
# ДИНАМИКА ПРОДАЖ (по дням)
# ============================================================

def get_daily_dynamics(db, days=7):
    """Динамика продаж (qty, revenue, margin) по дням."""
    start_date, end_date = _period_days(days)
    q = text("""
        SELECT
            DATE(inv.created_at) AS day,
            SUM(ii.qty_final) AS qty,
            SUM(ii.line_total_final) AS revenue,
            SUM((ii.unit_price_final - ii.unit_price_net_cost) * ii.qty_final) AS margin
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled'
        GROUP BY DATE(inv.created_at)
        ORDER BY DATE(inv.created_at);
    """)
    return [dict(r) for r in db.execute(q, {"start_date": start_date, "end_date": end_date}).mappings().all()]


# ============================================================
# ДИНАМИКА ТОП/АНТиТОП ПРОДАВЦОВ И ТОВАРОВ
# ============================================================

def get_entity_dynamics(db, days=7, entity="seller", asc=False):
    """
    Динамика для топ/антитоп продавцов, торговцев или товаров.
    entity = 'seller', 'salesperson' или 'product'
    asc = False (топ), True (антитоп)
    """
    start_date, end_date = _period_days(days)
    order = "ASC" if asc else "DESC"

    if entity == "seller":
        id_field = "ii.seller_id"
        name_field = "COALESCE(ii.seller_name, s.name)"
        join_extra = "LEFT JOIN sellers s ON s.id = ii.seller_id"
    elif entity == "salesperson":
        id_field = "ii.salesperson_id"
        name_field = "COALESCE(ii.salesperson_name, sp.name)"
        join_extra = "LEFT JOIN salespersons sp ON sp.id = ii.salesperson_id"
    else:
        id_field = "ii.product_id"
        name_field = "ii.product_name"
        join_extra = ""

    q = text(f"""
        WITH top_entities AS (
            SELECT {id_field} AS id
            FROM invoice_items ii
            JOIN invoices inv ON inv.id = ii.invoice_id
            {join_extra}
            WHERE inv.created_at BETWEEN :start_date AND :end_date
              AND inv.status <> 'cancelled'
            GROUP BY {id_field}
            ORDER BY SUM(ii.line_total_final) {order}
            LIMIT 10
        )
        SELECT
            DATE(inv.created_at) AS day,
            {name_field} AS name,
            SUM(ii.qty_final) AS qty,
            SUM(ii.line_total_final) AS revenue,
            SUM((ii.unit_price_final - ii.unit_price_net_cost) * ii.qty_final) AS margin
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        {join_extra}
        JOIN top_entities t ON t.id = {id_field}
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled'
        GROUP BY day, {name_field}
        ORDER BY day, {name_field};
    """)
    return [dict(r) for r in db.execute(q, {"start_date": start_date, "end_date": end_date}).mappings().all()]


# ============================================================
# 🆕 ДОП. МЕТРИКИ: AOV, СРЕД. КОРЗИНА, КАТЕГОРИИ, HEATMAP
# ============================================================

def get_avg_order_value(db, start_date, end_date):
    """🆕 Средний чек (AOV) = выручка / количество уникальных заказов."""
    q = text("""
        SELECT
            COALESCE(SUM(ii.line_total_final), 0) AS revenue,
            COUNT(DISTINCT ii.invoice_id) AS orders
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled';
    """)
    row = db.execute(q, {"start_date": start_date, "end_date": end_date}).mappings().first()
    revenue = float(row["revenue"] or 0)
    orders = int(row["orders"] or 0)
    return revenue / orders if orders else 0.0


def get_avg_basket_size(db, start_date, end_date):
    """🆕 Средняя корзина (SKU/заказ). Здесь считаем как среднее количество единиц товара на заказ."""
    q = text("""
        SELECT
            COALESCE(SUM(ii.qty_final), 0) AS total_qty,
            COUNT(DISTINCT ii.invoice_id) AS orders
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled';
    """)
    row = db.execute(q, {"start_date": start_date, "end_date": end_date}).mappings().first()
    total_qty = float(row["total_qty"] or 0)
    orders = int(row["orders"] or 0)
    return total_qty / orders if orders else 0.0


def get_top_categories(db, start_date, end_date, limit=10):
    """🆕 Топ категорий с вкладом в выручку (%)"""
    q = text("""
        WITH base AS (
            SELECT
                c.name AS name,
                SUM(ii.line_total_final) AS revenue
            FROM invoice_items ii
            JOIN invoices inv ON inv.id = ii.invoice_id
            LEFT JOIN products p ON p.id = ii.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE inv.created_at BETWEEN :start_date AND :end_date
              AND inv.status <> 'cancelled'
            GROUP BY c.name
        )
        SELECT
            name,
            revenue,
            CASE WHEN (SELECT COALESCE(SUM(revenue),0) FROM base) = 0 THEN 0
                 ELSE revenue * 100.0 / (SELECT SUM(revenue) FROM base)
            END AS share_pct
        FROM base
        ORDER BY revenue DESC
        LIMIT :limit;
    """)
    return [dict(r) for r in db.execute(q, {"start_date": start_date, "end_date": end_date, "limit": limit}).mappings().all()]


def get_hourly_heatmap(db, start_date, end_date):
    """
    🆕 Тепловая карта: выручка по дням недели (0=Пн..6=Вс) и часам (0..23).
    Возвращает список словарей: {'dow': 0..6, 'hour': 0..23, 'revenue': ...}
    """
    q = text("""
        SELECT
            CAST(EXTRACT(DOW FROM inv.created_at) AS INT) AS dow,  -- 0=Вc в PG, нормализуем ниже
            CAST(EXTRACT(HOUR FROM inv.created_at) AS INT) AS hour,
            SUM(ii.line_total_final) AS revenue
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        WHERE inv.created_at BETWEEN :start_date AND :end_date
          AND inv.status <> 'cancelled'
        GROUP BY 1, 2;
    """)
    # В Postgres DOW: 0=Sunday..6=Saturday → преобразуем к 0=Пн..6=Вс
    rows = [dict(r) for r in db.execute(q, {"start_date": start_date, "end_date": end_date}).mappings().all()]
    for r in rows:
        pg_dow = r["dow"]
        # Преобразование: Пн=1 → 0; Вт=2→1; ...; Вс=0→6
        r["dow"] = (pg_dow - 1) % 7
        r["revenue"] = float(r["revenue"] or 0.0)
    return rows
