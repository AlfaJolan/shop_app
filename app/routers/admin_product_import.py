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
            "success": None,
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

    Почему def, а не async def:
    - импорт файла, Excel и скачивание картинок — это блокирующие операции;
    - FastAPI выполнит такой endpoint в threadpool;
    - пользователь дождется результата сразу;
    - при этом event loop не будет блокироваться для остальных запросов.
    """

    # ---- Проверка наличия файла ----
    if not file or not file.filename:
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": "Файл не выбран.",
                "success": None,
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
                "success": None,
            },
            status_code=400,
        )

    try:
        service = ProductImportService(db)

        # ---- Импорт выполняется сразу, без background task ----
        result = service.import_from_upload(file)

        # ---- Успешный ответ с результатом импорта ----
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": result,
                "error": None,
                "success": "Импорт успешно завершен.",
            },
        )

    except ValueError as exc:
        # ---- Ошибки валидации (например, нет нужного листа или колонок) ----
        db.rollback()

        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": f"Ошибка импорта: {str(exc)}",
                "success": None,
            },
            status_code=400,
        )

    except Exception as exc:
        # ---- Любая другая ошибка ----
        db.rollback()
        print("IMPORT ERROR:", exc)

        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": "Неожиданная ошибка при импорте. Проверьте файл или логи.",
                "success": None,
            },
            status_code=500,
        )