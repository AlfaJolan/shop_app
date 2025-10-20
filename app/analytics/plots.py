# app/analytics/plots.py
import io
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.dates as mdates
import numpy as np


def _format_kzt(x, _):
    """Формат оси Y в тенге (с пробелами и ₸)."""
    return f"{int(x):,}".replace(",", " ") + " ₸"


def _prepare_figure(title: str, figsize=(8, 4)):
    """Создаёт фигуру с единым стилем."""
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")
    ax.set_title(title, fontsize=14, pad=14, fontweight="bold", color="#2c3e50")
    ax.yaxis.set_major_formatter(FuncFormatter(_format_kzt))
    ax.grid(alpha=0.25, color="#bdc3c7", linestyle="--", linewidth=0.7)
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

    fig, ax = _prepare_figure(f"📈 Динамика продаж за {days_label} дней", figsize=(9, 4.5))

    # --- Подготовка данных ---
    days = [datetime.strptime(str(d["day"]), "%Y-%m-%d").date() for d in data]
    revenue = [float(d["revenue"]) for d in data]
    margin = [float(d["margin"]) for d in data]

    # --- Построение графика ---
    ax.plot(
        days, revenue,
        color="#e74c3c",
        marker="o",
        linewidth=2.2,
        label="Выручка",
        alpha=0.9
    )
    ax.plot(
        days, margin,
        color="#2980b9",
        marker="D",
        linewidth=1.8,
        linestyle="--",
        label="Маржа",
        alpha=0.85
    )

    # --- Оформление осей ---
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
    plt.xticks(rotation=45, ha="right", fontsize=9)
    ax.set_xlabel("Дата", fontsize=10, color="#2c3e50")
    ax.set_ylabel("₸", fontsize=10, color="#2c3e50")
    ax.legend(frameon=True, loc="upper left", fontsize=9)
    ax.tick_params(axis='both', labelsize=9, colors="#2c3e50")

    fig.tight_layout()

    # --- Сохранение ---
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=220)
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

    # --- Подготовка данных ---
    names = [d["name"] for d in data]
    values = [float(d[value_key]) for d in data]

    if not top:
        names.reverse()
        values.reverse()

    # --- Автоматическая высота графика ---
    fig_height = max(4.5, len(names) * 0.6)
    fig, ax = _prepare_figure(title, figsize=(10, fig_height))

    # --- Бары ---
    color = "#3498db" if top else "#e74c3c"
    bars = ax.barh(range(len(names)), values, color=color, alpha=0.9, edgecolor="#2c3e50")

    # --- Настоящие подписи оси Y ---
    ax.set_yticks(range(len(names)))
    # сокращаем длинные подписи
    clean_names = [n if len(n) <= 25 else n[:25] + "…" for n in names]
    ax.set_yticklabels(clean_names, fontsize=10, color="#2c3e50", ha="right")

    # --- Подписи справа от баров ---
    for i, (bar, val) in enumerate(zip(bars, values)):
        ax.text(
            val + max(values) * 0.01,
            i,
            f"{int(val):,} ₸".replace(",", " "),
            va="center",
            fontsize=9.5,
            color="#2c3e50",
            fontweight="medium"
        )

    # --- Оформление ---
    ax.invert_yaxis()  # Топ-1 сверху
    ax.xaxis.set_major_formatter(FuncFormatter(_format_kzt))
    ax.set_xlabel("Выручка (₸)", fontsize=10, color="#2c3e50")
    ax.tick_params(axis='x', labelsize=9, colors="#2c3e50")
    ax.grid(alpha=0.25, linestyle="--", linewidth=0.7)

    plt.subplots_adjust(left=0.35, right=0.98)
    fig.tight_layout()

    # --- Сохранение ---
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=220)
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

    fig, ax = _prepare_figure(title, figsize=(6, 6))
    cities = [d["city"] for d in data]
    revenues = [float(d["revenue"]) for d in data]

    # --- Цвета ---
    colors = plt.cm.tab20(np.linspace(0, 1, len(cities)))

    wedges, texts, autotexts = ax.pie(
        revenues,
        labels=cities,
        autopct=lambda p: f"{p:.1f}%" if p > 4 else "",
        startangle=90,
        colors=colors,
        textprops={"fontsize": 9, "color": "#2c3e50"},
        wedgeprops={"edgecolor": "white", "linewidth": 0.7}
    )

    ax.legend(
        wedges,
        [f"{c}: {int(r):,} ₸".replace(',', ' ') for c, r in zip(cities, revenues)],
        title="Города",
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        fontsize=8.5
    )

    ax.axis("equal")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=220)
    plt.close(fig)
    buf.seek(0)
    return buf
