# app/analytics/plots.py
import io
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.dates as mdates


def _format_kzt(x, _):
    """Формат оси Y в тенге (с пробелами и ₸)."""
    return f"{int(x):,}".replace(",", " ") + " ₸"


def _prepare_figure(title: str, figsize=(8, 4)):
    """Создаёт фигуру с единым стилем."""
    plt.style.use("seaborn-v0_8-colorblind")
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_title(title, fontsize=13, pad=12, fontweight="bold")
    ax.yaxis.set_major_formatter(FuncFormatter(_format_kzt))
    ax.grid(alpha=0.3)
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

    fig, ax = _prepare_figure(f"📈 Динамика продаж за {days_label} дней")

    # --- Подготовка данных ---
    days = [datetime.strptime(str(d["day"]), "%Y-%m-%d").date() for d in data]
    revenue = [float(d["revenue"]) for d in data]
    margin = [float(d["margin"]) for d in data]

    # --- Построение графика ---
    ax.plot(days, revenue, color="#E74C3C", marker="o", linewidth=2, label="Выручка")
    ax.plot(days, margin, color="#2980B9", marker="o", linewidth=1.8, linestyle="--", label="Маржа")

    # --- Оформление осей ---
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
    plt.xticks(rotation=45, ha="right", fontsize=9)

    ax.set_xlabel("Дата", fontsize=10)
    ax.set_ylabel("₸", fontsize=10)
    ax.legend(frameon=True, loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()

    # --- Сохранение ---
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=200)
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
    bars = ax.barh(names, values, color="#1E88E5" if top else "#E74C3C")

    # Добавляем подписи на барах
    ax.bar_label(bars, labels=[f"{v:,.0f} ₸".replace(",", " ") for v in values],
                 padding=3, fontsize=9)

    ax.xaxis.set_major_formatter(FuncFormatter(_format_kzt))
    ax.set_xlabel("₸", fontsize=10)
    ax.invert_yaxis()  # чтобы топ-1 был сверху

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=200)
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

    # Немного ярче палитра
    colors = plt.cm.Paired(range(len(cities)))

    ax.pie(
        revenues,
        labels=cities,
        autopct="%1.1f%%",
        startangle=90,
        colors=colors,
        textprops={"fontsize": 9}
    )
    ax.axis("equal")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    buf.seek(0)
    return buf
