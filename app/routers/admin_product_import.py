from fastapi import APIRouter, Request, Depends, UploadFile, File
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.product_import_service import ProductImportService

router = APIRouter(
    prefix="/admin/catalog/products/import",
    tags=["admin-product-import"],
)

templates = Jinja2Templates(directory="app/templates")


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


@router.get("/")
def product_import_page(request: Request):
    """
    Страница загрузки Excel.
    По умолчанию result = None (еще ничего не импортировали).
    """
    return templates.TemplateResponse(
        "admin/product_import.html",
        {
            "request": request,
            "result": None,
            "error": None,
        },
    )


@router.post("/")
def product_import_submit(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Обработка загрузки Excel:

    1. Проверяем файл
    2. Передаем в ProductImportService
    3. Возвращаем result в шаблон

    Важно:
    - result.errors → критичные ошибки (строки не импортированы)
    - result.warnings → некритичные (например, не скачалось фото)
    """

    # ---- Проверка наличия файла ----
    if not file or not file.filename:
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": "Файл не выбран.",
            },
        )

    # ---- Проверка формата ----
    if not file.filename.lower().endswith(".xlsx"):
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": "Поддерживаются только Excel-файлы формата .xlsx",
            },
            status_code=400,
        )

    try:
        # ---- Запуск импорта ----
        service = ProductImportService(db)
        result = service.import_from_upload(file)

        # ---- Возвращаем результат ----
        # В result уже есть:
        # - errors
        # - warnings
        # - статистика
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": result,
                "error": None,
            },
        )

    except ValueError as exc:
        # ---- Ошибки валидации (например, нет нужного листа или колонок) ----
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": f"Ошибка импорта: {str(exc)}",
            },
            status_code=400,
        )

    except Exception as exc:
        # ---- Любая другая ошибка ----
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": "Неожиданная ошибка при импорте. Проверьте файл или логи.",
            },
            status_code=500,
        )