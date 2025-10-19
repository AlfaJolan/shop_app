# app/analytics/plots.py
import io
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


def _format_kzt(x, _):
    """Формат оси Y в тенге (с пробелами и ₸)."""
    return f"{int(x):,}".replace(",", " ") + " ₸"


def _prepare_figure(title: str, figsize=(8, 4)):
    """Создаёт фигуру с единым стилем."""
    plt.style.use("ggplot")
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_title(title, fontsize=12, pad=10, fontweight="bold")
    ax.yaxis.set_major_formatter(FuncFormatter(_format_kzt))
    return fig, ax


# ============================================================
# 📈 1. ДИНАМИКА ПРОДАЖ ПО ДНЯМ
# ============================================================

def plot_sales_dynamics(data: list[dict], days_label: str = "7"):
    """
    Рисует график выручки и маржи по дням.
    data: [{'day': date, 'revenue': ..., 'margin': ...}, ...]
    """
    if not data:
        return None

    fig, ax = _prepare_figure(f"Динамика продаж за {days_label} дней")

    days = [d["day"] for d in data]
    revenue = [float(d["revenue"]) for d in data]
    margin = [float(d["margin"]) for d in data]

    ax.plot(days, revenue, marker="o", label="Выручка")
    ax.plot(days, margin, marker="o", label="Маржа", linestyle="--")

    ax.legend()
    ax.set_xlabel("Дата")
    ax.set_ylabel("₸")
    ax.grid(True, alpha=0.4)

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# 📊 2. ТОП/АНТиТОП ГРАФИК (BAR)
# ============================================================

def plot_bar_top(data: list[dict], title: str, value_key="revenue", top=True):
    """
    Рисует горизонтальный bar chart для топа или антитопа.
    data: [{'name': ..., 'revenue': ...}, ...]
    """
    if not data:
        return None

    names = [d["name"] for d in data]
    values = [float(d[value_key]) for d in data]

    if not top:
        names.reverse()
        values.reverse()

    fig, ax = _prepare_figure(title, figsize=(8, 5))
    ax.barh(names, values, color="#1f77b4" if top else "#d62728")
    ax.xaxis.set_major_formatter(FuncFormatter(_format_kzt))
    ax.set_xlabel("₸")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# 🥧 3. ГРАФИК ГОРОДОВ (PIE)
# ============================================================

def plot_city_pie(data: list[dict], title="Продажи по городам"):
    """
    Рисует круговую диаграмму продаж по городам.
    data: [{'city': ..., 'revenue': ...}, ...]
    """
    if not data:
        return None

    fig, ax = _prepare_figure(title, figsize=(5, 5))
    cities = [d["city"] for d in data]
    revenues = [float(d["revenue"]) for d in data]
    ax.pie(revenues, labels=cities, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
