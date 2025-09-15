# app/routers/invoice.py
from decimal import Decimal
from io import BytesIO
import os
from urllib.parse import quote  # ← для RFC 5987

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.invoice import Invoice

# ===== PDF =====
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ===== XLSX =====
from openpyxl import Workbook
try:
    from openpyxl.drawing.image import Image as XLImage
    PIL_OK = True
except Exception:
    PIL_OK = False  # Pillow не установлен — картинки в xlsx пропустим

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


def _get_invoice_checked(db: Session, invoice_id: int, pkey: str) -> Invoice:
    """Проверка pkey и получение накладной."""
    inv = db.query(Invoice).get(invoice_id)
    if not inv or inv.is_revoked or not inv.pkey or pkey != inv.pkey:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


def _register_font():
    """Регистрируем шрифт (DejaVu). Если нужен знак ₸ — поставь NotoSans-Regular.ttf и замени имя."""
    try:
        pdfmetrics.getFont("DejaVu")
    except Exception:
        font_path = "app/static/fonts/DejaVuSans.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("DejaVu", font_path))


def _content_disposition_utf8(pretty_filename_utf8: str, fallback_ascii: str) -> str:
    """
    Content-Disposition с ASCII-фолбэком и UTF-8 вариантом по RFC 5987.
    Заголовки должны быть latin-1 — поэтому UTF-8 имя экранируем.
    """
    return "attachment; filename=\"{fallback}\"; filename*=UTF-8''{utf8}".format(
        fallback=fallback_ascii.replace('"', ''),
        utf8=quote(pretty_filename_utf8, safe="")
    )


@router.get("/invoice/{invoice_id}", response_class=HTMLResponse)
def invoice_public(
    request: Request,
    invoice_id: int,
    pkey: str = Query(...),
    db: Session = Depends(get_db),
):
    inv = _get_invoice_checked(db, invoice_id, pkey)
    return templates.TemplateResponse("public/invoice.html", {"request": request, "inv": inv})


# ---------- PDF ----------
@router.get("/invoice/{invoice_id}/export.pdf")
def invoice_export_pdf(
    invoice_id: int,
    pkey: str = Query(...),
    db: Session = Depends(get_db),
):
    inv = _get_invoice_checked(db, invoice_id, pkey)
    _register_font()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DejaTitle", parent=styles["Title"], fontName="DejaVu"))
    styles.add(ParagraphStyle(name="Deja", parent=styles["Normal"], fontName="DejaVu"))
    styles.add(ParagraphStyle(
        name="DejaWrap",
        parent=styles["Normal"],
        fontName="DejaVu",
        wordWrap="CJK",   # перенос строк
        fontSize=9,
        leading=11,
    ))

    elems = []
    elems.append(Paragraph(f"Накладная № {inv.id}", styles["DejaTitle"]))

    # Шапка
    meta = (
        f"Имя: {inv.customer_name or '—'}<br/>"
        f"Телефон: {inv.phone or '—'}<br/>"
        f"Время: {inv.created_at.strftime('%Y-%m-%d %H:%M')}"
    )
    elems += [Spacer(1, 8), Paragraph(meta, styles["Deja"]), Spacer(1, 12)]

    # Таблица
    data = [[
        Paragraph("Наименование", styles["DejaWrap"]),
        Paragraph("Продавец", styles["DejaWrap"]),
        Paragraph("Фото", styles["DejaWrap"]),
        Paragraph("Вариант", styles["DejaWrap"]),
        Paragraph("Кол-во", styles["DejaWrap"]),
        Paragraph("Цена", styles["DejaWrap"]),00000
        Paragraph("Сумма", styles["DejaWrap"]),
    ]]

    for it in inv.items:
        # миниатюра
        img_flow = ""
        if it.product_image:
            fs_path = os.path.join("app", "static", "uploads", "products", it.product_image)
            if os.path.exists(fs_path):
                try:
                    img_flow = RLImage(fs_path, width=40, height=40)
                except Exception:
                    img_flow = ""

        qty = int(it.qty_final)
        price = Decimal(str(it.unit_price_final))
        summ = Decimal(str(it.line_total_final))

        data.append([
            Paragraph(it.product_name + ", " + it.variant_name or "—", styles["DejaWrap"]),
            Paragraph(it.seller_name or "—", styles["DejaWrap"]),
            img_flow,
            Paragraph(it.variant_name or "—", styles["DejaWrap"]),
            Paragraph(str(qty), styles["DejaWrap"]),
            Paragraph(f"{price:.2f} ₸", styles["DejaWrap"]),
            Paragraph(f"{summ:.2f} ₸", styles["DejaWrap"]),
        ])

    data.append([
        "", "", "", "",
        Paragraph("Итого:", styles["DejaWrap"]),
        Paragraph(f"{Decimal(str(inv.total_amount_final)):.2f} ₸", styles["DejaWrap"]),
    ])

    table = Table(data, colWidths=[150, 50, 100, 50, 70, 80])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 1), (5, -2), "RIGHT"),
        ("ALIGN", (4, -1), (5, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    elems.append(table)

    doc.build(elems)
    buf.seek(0)

    # Имя файла
    date_str = inv.created_at.strftime("%Y-%m-%d_%H-%M")
    name = (inv.customer_name or "Клиент").strip()
    phone = (inv.phone or "без_телефона").strip()

    pretty = f"Накладная {name} {phone} {date_str}.pdf"
    fallback = f"nakladnaya_{inv.id}_{date_str}.pdf"

    headers = {"Content-Disposition": _content_disposition_utf8(pretty, fallback)}
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)


# ---------- XLSX ----------
@router.get("/invoice/{invoice_id}/export.xlsx")
def invoice_export_xlsx(
    invoice_id: int,
    pkey: str = Query(...),
    db: Session = Depends(get_db),
):
    inv = _get_invoice_checked(db, invoice_id, pkey)

    wb = Workbook()
    ws = wb.active
    ws.title = "Накладная"

    ws.append([f"Накладная № {inv.id}"])
    ws.append(["Имя", inv.customer_name or "—"])
    ws.append(["Телефон", inv.phone or "—"])
    ws.append(["Время", inv.created_at.strftime("%Y-%m-%d %H:%M")])
    ws.append([])

    ws.append(["Наименование","Продавец", "Фото", "Вариант", "Кол-во", "Цена", "Сумма"])

    row = ws.max_row + 1
    for it in inv.items:
        ws.append([
            it.product_name + ", " + it.variant_name,
            it.seller_name,
            "",  # под картинку
            it.variant_name,
            int(it.qty_final),
            float(it.unit_price_final),
            float(it.line_total_final),
        ])
        if PIL_OK and it.product_image:
            fs_path = os.path.join("app", "static","uploads","products", it.product_image)
            if os.path.exists(fs_path):
                try:
                    img = XLImage(fs_path)
                    img.width = 40
                    img.height = 40
                    ws.add_image(img, f"C{row}")   # картинка во 2-й столбец
                    ws.row_dimensions[row].height = 34
                except Exception:
                    pass
        row += 1

    ws.append([])
    ws.append(["", "", "", "", "Итого:", float(inv.total_amount_final)])

    # ширина колонок
    ws.column_dimensions["A"].width = 28  # Наименование
    ws.column_dimensions["B"].width = 8   # Фото
    ws.column_dimensions["C"].width = 18  # Вариант

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    # Имя файла: «Накладная Имя Телефон Дата.xlsx» + ASCII fallback
    date_str = inv.created_at.strftime("%Y-%m-%d_%H-%M")
    name = (inv.customer_name or "Клиент").strip()
    phone = (inv.phone or "без_телефона").strip()

    pretty = f"Накладная {name} {phone} {date_str}.xlsx"
    fallback = f"nakladnaya_{inv.id}_{date_str}.xlsx"

    headers = {"Content-Disposition": _content_disposition_utf8(pretty, fallback)}
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
