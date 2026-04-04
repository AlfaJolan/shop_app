from fastapi import APIRouter, Request, Depends, UploadFile, File, BackgroundTasks
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


# 🔹 Оптимизация: выносим импорт в фон, чтобы не блокировать HTTP-запрос
def run_import_in_background(file_bytes: bytes):
    db = SessionLocal()
    try:
        service = ProductImportService(db)

        # 🔹 создаем UploadFile-подобный объект из байтов (чтобы не ломать сервис)
        from io import BytesIO
        fake_file = BytesIO(file_bytes)
        fake_file.filename = "import.xlsx"

        service.import_from_upload(fake_file)

    except Exception as e:
        print("IMPORT ERROR:", e)

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
async def product_import_submit(
    request: Request,
    background_tasks: BackgroundTasks,
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
        # 🔹 Оптимизация: читаем файл один раз в память (избегаем медленного stream IO)
        file_bytes = await file.read()

        # 🔹 Запускаем импорт в фоне (не блокируем пользователя)
        background_tasks.add_task(run_import_in_background, file_bytes)

        # ---- Возвращаем быстрый ответ ----
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": None,
                "success": "Импорт запущен в фоне. Результат будет доступен позже.",
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