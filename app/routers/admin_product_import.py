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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def product_import_page(request: Request):
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
    if not file or not file.filename:
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": "Файл не выбран.",
            },
        )

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
        service = ProductImportService(db)
        result = service.import_from_upload(file)

        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": result,
                "error": None,
            },
        )

    except Exception as exc:
        return templates.TemplateResponse(
            "admin/product_import.html",
            {
                "request": request,
                "result": None,
                "error": f"Ошибка импорта: {str(exc)}",
            },
            status_code=400,
        )