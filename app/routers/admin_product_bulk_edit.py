from io import BytesIO

from fastapi import APIRouter, Request, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.audit import get_actor
from app.services.product_bulk_excel_service import ProductBulkExcelService


router = APIRouter(
    prefix="/admin/catalog/products/bulk-edit",
    tags=["admin-product-bulk-edit"],
)

templates = Jinja2Templates(directory="app/templates")

# 🔹 Ограничение на размер загружаемого Excel
# Этого более чем достаточно для bulk-редактирования каталога.
MAX_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB


def get_db():
    """
    Dependency для получения DB-сессии.
    Каждому запросу — своя сессия.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def render_bulk_edit_page(
    request: Request,
    *,
    result=None,
    error: str | None = None,
    success: str | None = None,
    status_code: int = 200,
):
    """
    Общий helper для отрисовки страницы bulk edit.
    Чтобы не дублировать один и тот же TemplateResponse в каждом месте.
    """
    return templates.TemplateResponse(
        "admin/product_bulk_edit.html",
        {
            "request": request,
            "result": result,
            "error": error,
            "success": success,
        },
        status_code=status_code,
    )


@router.get("/")
def product_bulk_edit_page(request: Request):
    """
    Страница массового редактирования каталога через Excel.

    Здесь пользователь:
    1. Скачивает Excel-файл
    2. Меняет нужные поля локально
    3. Загружает файл обратно
    """
    return render_bulk_edit_page(request)


@router.get("/export")
def product_bulk_edit_export(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Выгрузка каталога в Excel для массового редактирования.

    Почему роут остается тонким:
    - не содержит SQL-логики;
    - не занимается openpyxl-логикой;
    - только получает actor, вызывает сервис и отдает файл.
    """
    try:
        actor = get_actor(request, db)
        service = ProductBulkExcelService(db)

        workbook_bytes, filename = service.export_catalog_excel(actor=actor)

        return StreamingResponse(
            BytesIO(workbook_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    except ValueError as exc:
        db.rollback()
        return render_bulk_edit_page(
            request,
            error=f"Ошибка экспорта: {str(exc)}",
            status_code=400,
        )

    except Exception as exc:
        db.rollback()
        print("BULK EXPORT ERROR:", exc)

        raise HTTPException(
            status_code=500,
            detail="Не удалось сформировать Excel-файл для массового редактирования.",
        )


@router.post("/import")
def product_bulk_edit_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Загрузка обратно Excel-файла для массового обновления каталога.

    Почему так безопаснее:
    - в роуте только базовые проверки;
    - файл читается один раз и быстро закрывается;
    - тяжелая валидация и изменения идут в сервисе;
    - все изменения в БД должны коммититься только в сервисе и только один раз.
    """

    # ---- Проверка наличия файла ----
    if not file or not file.filename:
        return render_bulk_edit_page(
            request,
            error="Файл не выбран.",
            status_code=400,
        )

    filename = (file.filename or "").strip()

    # ---- Проверка расширения ----
    if not filename.lower().endswith(".xlsx"):
        return render_bulk_edit_page(
            request,
            error="Поддерживаются только Excel-файлы формата .xlsx",
            status_code=400,
        )

    try:
        # ---- Читаем файл в память один раз ----
        file_bytes = file.file.read()

        # ---- Сразу закрываем UploadFile, чтобы не держать ресурс ----
        try:
            file.file.close()
        except Exception:
            pass

        # ---- Проверка на пустой файл ----
        if not file_bytes:
            return render_bulk_edit_page(
                request,
                error="Файл пустой.",
                status_code=400,
            )

        # ---- Ограничение размера файла ----
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            return render_bulk_edit_page(
                request,
                error="Файл слишком большой. Используйте Excel до 15 MB.",
                status_code=400,
            )

        actor = get_actor(request, db)
        service = ProductBulkExcelService(db)

        result = service.import_catalog_excel(
            file_bytes=file_bytes,
            original_filename=filename,
            actor=actor,
        )

        return render_bulk_edit_page(
            request,
            result=result,
            success="Массовое обновление каталога успешно завершено.",
        )

    except ValueError as exc:
        db.rollback()

        return render_bulk_edit_page(
            request,
            error=f"Ошибка импорта: {str(exc)}",
            status_code=400,
        )

    except Exception as exc:
        db.rollback()
        print("BULK IMPORT ERROR:", exc)

        return render_bulk_edit_page(
            request,
            error="Неожиданная ошибка при массовом обновлении. Проверьте файл или логи.",
            status_code=500,
        )