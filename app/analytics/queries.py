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
    Динамика для топ/антитоп продавцов или товаров.
    entity = 'seller' или 'product'
    asc = False (топ), True (антитоп)
    """
    start_date, end_date = _period_days(days)
    order = "ASC" if asc else "DESC"

    if entity == "seller":
        id_field = "ii.seller_id"
        name_field = "COALESCE(ii.seller_name, s.name)"
        join_extra = "LEFT JOIN sellers s ON s.id = ii.seller_id"
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
