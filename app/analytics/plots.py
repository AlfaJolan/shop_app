# app/analytics/plots.py
import io
from datetime import datetime
# === Фикс emoji warning (Arial не поддерживает эмодзи) ===
import matplotlib
matplotlib.rcParams["font.family"] = "DejaVu Sans"        # ✅ кириллица + emoji
matplotlib.rcParams["axes.unicode_minus"] = False          # чтобы "–" отображался корректно
import warnings
warnings.filterwarnings("ignore", message="Glyph.*missing")  # необязательно, просто тише лог
# ==========================================================
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.dates as mdates
import numpy as np


def _format_kzt(x, _):
    """Формат оси Y в тенге (с пробелами и ₸)."""
    return f"{int(x):,}".replace(",", " ") + " ₸"


def _prepare_figure(title: str, figsize=(8, 4)):
    """Создаёт фигуру с единым стилем."""
    plt.rcParams["font.family"] = "DejaVu Sans"   # 🆕 исправляет предупреждение о глифах
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

    # 🆕 unified canvas size для Telegram (≈1400×500 px)
    fig, ax = _prepare_figure(f"📈 Динамика продаж за {days_label} дней", figsize=(14, 5))  # 🆕

    # --- Подготовка данных ---
    days = [datetime.strptime(str(d["day"]), "%Y-%m-%d").date() for d in data]
    revenue = [float(d["revenue"]) for d in data]
    margin = [float(d["margin"]) for d in data]

    # 🆕 Субтайтл с диапазоном дат (например: за 30 дней: 21.09–20.10)
    if days:
        start_lbl = min(days).strftime("%d.%m")
        end_lbl = max(days).strftime("%d.%m")
        ax.text(
            0.01, 1.02, f"за {days_label} дней: {start_lbl}–{end_lbl}",
            transform=ax.transAxes, fontsize=12, color="#7f8c8d"
        )

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

    # 🆕 ➕ Added SMA(7) and trend line
    y = np.array(revenue, dtype=float)
    if len(y) >= 3:
        win = 7 if len(y) >= 7 else max(3, (len(y)//2)*2 + 1)  # нечётное окно
        sma = np.convolve(y, np.ones(win)/win, mode="valid")
        sma_x = days[win - 1:]
        ax.plot(sma_x, sma, linewidth=2.0, alpha=0.9, label=f"SMA({win})")

    if len(y) >= 2:
        x = mdates.date2num(days)
        coeffs = np.polyfit(x, y, 1)
        trend = np.poly1d(coeffs)(x)
        ax.plot(days, trend, linewidth=1.5, alpha=0.7, label="Тренд")

    # 🆕 ⚠️ Annotate anomalies (±15% from mean)
    if len(y) >= 3:
        mean_val = np.mean(y)
        for d, val in zip(days, y):
            delta = (val - mean_val) / mean_val * 100 if mean_val else 0
            if abs(delta) >= 15:
                ax.annotate(
                    f"{delta:+.0f}%",
                    xy=(d, val),
                    xytext=(0, 10),
                    textcoords="offset points",
                    fontsize=10,
                    color="#2c3e50",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#fff", ec="#e0e0e0", lw=0.6),
                    arrowprops=dict(arrowstyle="-", lw=0.8, color="#7f8c8d")
                )

    # --- Оформление осей ---
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
    plt.xticks(rotation=45, ha="right", fontsize=12)  # ⚙️ 12px оси
    ax.set_xlabel("Дата", fontsize=12, color="#2c3e50")  # ⚙️ 12px оси
    ax.set_ylabel("₸", fontsize=12, color="#2c3e50")     # ⚙️ 12px оси
    ax.legend(frameon=True, loc="upper left", fontsize=12)  # ⚙️ 12px легенда
    ax.tick_params(axis='both', labelsize=12, colors="#2c3e50")  # ⚙️ 12px оси

    fig.tight_layout()

    # --- Сохранение ---
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)  # 🆕 dpi=100 при figsize=(14,5) ≈ 1400×500
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
    fig, ax = _prepare_figure(title, figsize=(14, fig_height))  # 🆕 ширина 14 для читаемости

    # --- Бары ---
    color = "#3498db" if top else "#e74c3c"
    bars = ax.barh(range(len(names)), values, color=color, alpha=0.9, edgecolor="#2c3e50")

    # --- Настоящие подписи оси Y ---
    ax.set_yticks(range(len(names)))
    # сокращаем длинные подписи
    clean_names = [n if len(n) <= 25 else n[:25] + "…" for n in names]
    ax.set_yticklabels(clean_names, fontsize=12, color="#2c3e50", ha="right")  # ⚙️ 12px оси

    # --- Подписи справа от баров ---
    for i, (bar, val) in enumerate(zip(bars, values)):
        ax.text(
            val + (max(values) * 0.01 if values else 0.1),
            i,
            f"{int(val):,} ₸".replace(",", " "),
            va="center",
            fontsize=12,  # ⚙️ 12px
            color="#2c3e50",
            fontweight="medium"
        )

    # --- Оформление ---
    ax.invert_yaxis()  # Топ-1 сверху
    ax.xaxis.set_major_formatter(FuncFormatter(_format_kzt))
    ax.set_xlabel("Выручка (₸)", fontsize=12, color="#2c3e50")  # ⚙️ 12px
    ax.tick_params(axis='x', labelsize=12, colors="#2c3e50")    # ⚙️ 12px
    ax.grid(alpha=0.25, linestyle="--", linewidth=0.7)

    plt.subplots_adjust(left=0.35, right=0.98)
    fig.tight_layout()

    # --- Сохранение ---
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)  # 🆕 1400px ширины
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

    # 🆕 агрегируем «длинный хвост» в "Прочие" (<4.5%)
    rows = sorted([(d["city"], float(d["revenue"])) for d in data], key=lambda x: x[1], reverse=True)  # 🆕
    total = sum(v for _, v in rows) or 1  # 🆕
    major, minor = [], []  # 🆕
    for name, val in rows:  # 🆕
        if val / total < 0.045:
            minor.append(val)
        else:
            major.append((name, val))
    if minor:
        major.append(("Прочие", sum(minor)))  # 🆕

    cities = [n for n, _ in major]  # ⚙️ обновлено
    revenues = [v for _, v in major]  # ⚙️ обновлено

    fig, ax = _prepare_figure(title, figsize=(14, 5))  # 🆕 ширина 14 для единства DPI
    colors = plt.cm.tab20(np.linspace(0, 1, len(cities)))

    # ⚙️ Легенда вместо подписи на секторах — убираем labels и используем legend
    wedges, _ = ax.pie(
        revenues,
        startangle=90,
        colors=colors,
        textprops={"fontsize": 12, "color": "#2c3e50"},  # ⚙️ 12px
        wedgeprops={"edgecolor": "white", "linewidth": 0.7}
    )

    ax.legend(
        wedges,
        [f"{c}: {int(r):,} ₸ ({r/total*100:.1f}%)".replace(',', ' ') for c, r in zip(cities, revenues)],
        title="Города",
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        fontsize=12  # ⚙️ 12px
    )

    ax.axis("equal")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)  # 🆕 1400×500
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# 🆕 4. ТОП КАТЕГОРИЙ (BAR)
# ============================================================

def plot_top_categories(data: list[dict], title: str = "Топ категорий (вклад в выручку)"):
    """
    data: [{'name': 'Молочные', 'revenue': 12345.67, 'share_pct': 34.5}, ...]
    """
    if not data:
        return None

    names = [d["name"] for d in data]
    values = [float(d["revenue"]) for d in data]
    shares = [float(d.get("share_pct", 0)) for d in data]

    fig_height = max(4.5, len(names) * 0.6)
    fig, ax = _prepare_figure(title, figsize=(14, fig_height))  # 🆕

    bars = ax.barh(range(len(names)), values, color="#8e44ad", alpha=0.9, edgecolor="#2c3e50")  # 🆕

    ax.set_yticks(range(len(names)))
    clean_names = [n if len(n) <= 25 else n[:25] + "…" for n in names]
    ax.set_yticklabels(clean_names, fontsize=12, color="#2c3e50", ha="right")  # 🆕

    for i, (bar, val, pct) in enumerate(zip(bars, values, shares)):
        ax.text(
            val + (max(values) * 0.01 if values else 0.1),
            i,
            f"{int(val):,} ₸ ({pct:.1f}%)".replace(",", " "),
            va="center",
            fontsize=12,
            color="#2c3e50",
            fontweight="medium"
        )

    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(FuncFormatter(_format_kzt))
    ax.set_xlabel("Выручка (₸)", fontsize=12, color="#2c3e50")
    ax.tick_params(axis='x', labelsize=12, colors="#2c3e50")
    ax.grid(alpha=0.25, linestyle="--", linewidth=0.7)

    plt.subplots_adjust(left=0.35, right=0.98)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)  # 🆕
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# 🆕 5. ТЕПЛОВАЯ КАРТА СПРОСА (день × час)
# ============================================================
from matplotlib.colors import Normalize

def plot_heatmap_demand(matrix: np.ndarray, title: str = "Активность заказов по дням и часам (30 дней)"):
    """
    matrix: numpy (7 x 24) — значения (например, выручка) по [dow][hour]
    dow: 0=Пн ... 6=Вс
    """
    if matrix is None or matrix.size == 0:
        return None

    fig, ax = plt.subplots(figsize=(14, 5))
    plt.style.use("seaborn-v0_8-whitegrid")
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")

    # --- Построение тепловой карты через pcolormesh (поддерживает edgecolors)
    hours = np.arange(25)
    days = np.arange(8)
    pcm = ax.pcolormesh(
        hours, days, matrix,
        cmap="YlOrRd",              # 🎨 вернули теплую палитру (красно-желтая)
        edgecolors="white",         # ✅ видимая сетка
        linewidths=0.5,
        norm=Normalize(vmin=0, vmax=matrix.max() * 1.05 if matrix.max() > 0 else 1)  # 🆕 мягче контраст
    )

    # --- Оси и подписи ---
    days_labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    hours_labels = [f"{h:02d}" for h in range(24)]
    ax.set_yticks(np.arange(7) + 0.5)
    ax.set_yticklabels(days_labels, fontsize=12, color="#2c3e50")
    ax.set_xticks(np.arange(24) + 0.5)
    ax.set_xticklabels(hours_labels, fontsize=11, rotation=0, color="#2c3e50")

    ax.set_xlabel("Час", fontsize=12, color="#2c3e50")
    ax.set_ylabel("День недели", fontsize=12, color="#2c3e50")
    ax.set_title(title, fontsize=16, pad=14, fontweight="bold", color="#2c3e50")

    # --- Подписи чисел внутри ячеек ---
    max_val = np.max(matrix)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            if val <= 0:
                continue
            # 🆕 Контрастный текст: белый на насыщенном, тёмный на светлом
            intensity = val / max_val if max_val else 0
            text_color = "#ffffff" if intensity > 0.6 else "#2c3e50"
            text_val = f"{val/1000:.0f}k" if max_val >= 10000 else f"{int(val)}"
            ax.text(j + 0.5, i + 0.5, text_val, ha="center", va="center", fontsize=9, color=text_color)

    # --- Цветовая шкала ---
    cbar = fig.colorbar(pcm, ax=ax)
    cbar.ax.tick_params(labelsize=11)
    cbar.ax.set_title("₸", fontsize=12, color="#2c3e50", pad=6)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf



def plot_heatmap_demand2(matrix: np.ndarray, title: str = "Активность заказов по дням и часам"):
    """
    matrix: numpy (7 x 24) — значения (например, выручка) по [dow][hour]
            dow: 0=Пн ... 6=Вс
    """
    if matrix is None or matrix.size == 0:
        return None

    fig, ax = _prepare_figure(title, figsize=(14, 5))  # 🆕

    im = ax.imshow(matrix, aspect="auto", origin="upper", cmap="Blues")  # 🆕 спокойная палитра

    # подписи осей
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"], fontsize=12, color="#2c3e50")  # 🆕
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}" for h in range(24)], fontsize=12, rotation=0, color="#2c3e50")  # 🆕

    ax.set_xlabel("Час", fontsize=12, color="#2c3e50")
    ax.set_ylabel("День недели", fontsize=12, color="#2c3e50")

    # цветовая шкала
    cbar = fig.colorbar(im, ax=ax)
    cbar.ax.tick_params(labelsize=12)  # 🆕

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)  # 🆕 1400×500
    plt.close(fig)
    buf.seek(0)
    return buf

import io
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

def plot_salesperson_kpi_bars(data):
    """Бар-чарт: выручка и маржа по торговцам."""
    if not data:
        return None

    names = [d["name"] for d in data]
    revenue = [d["revenue"] for d in data]
    margin = [d["margin"] for d in data]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(names, revenue, label="Выручка", alpha=0.7)
    ax.bar(names, margin, label="Маржа", alpha=0.7)
    ax.set_title("KPI по торговцам", fontsize=14, pad=12)
    ax.set_ylabel("₸")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", " ")))
    ax.legend()
    plt.xticks(rotation=15)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf
