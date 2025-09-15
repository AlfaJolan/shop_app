from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Product, Category, Variant
import shutil
from pathlib import Path

router = APIRouter(prefix="/admin/catalog/products", tags=["admin-products"])
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = Path("app/static/uploads/products")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 📦 список товаров
@router.get("/")
def products_index(request: Request):
    db = next(get_db())
    products = db.query(Product).all()
    return templates.TemplateResponse("admin/products_index.html", {
        "request": request,
        "products": products,
    })


# 🆕 форма создания
@router.get("/new")
def product_new(request: Request):
    db = next(get_db())
    categories = db.query(Category).all()
    return templates.TemplateResponse("admin/product_form.html", {
        "request": request,
        "categories": categories,
        "product": None,
    })


# 💾 создание
@router.post("/create")
def product_create(
    request: Request,
    name: str = Form(...),
    sku: str = Form(None),
    category_id: int = Form(None),
    unit: str = Form("шт"),
    variants_name: list[str] = Form(...),
    variants_price: list[float] = Form(...),
    variants_stock: list[int] = Form(...),
    image: UploadFile = File(None),
):
    db = next(get_db())

    filename = None
    if image:
        filename = image.filename
        with open(UPLOAD_DIR / filename, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    product = Product(
        name=name, sku=sku, category_id=category_id,
        unit=unit, image=filename
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    for i in range(len(variants_name)):
        v = Variant(
            product_id=product.id,
            name=variants_name[i],
            unit_price=variants_price[i],
            stock=variants_stock[i],
        )
        db.add(v)

    db.commit()
    return RedirectResponse("/admin/catalog/products", status_code=303)


# ✏️ форма редактирования
@router.get("/{product_id}/edit")
def product_edit(product_id: int, request: Request):
    db = next(get_db())
    product = db.query(Product).get(product_id)
    categories = db.query(Category).all()
    return templates.TemplateResponse("admin/product_form.html", {
        "request": request,
        "product": product,
        "categories": categories,
    })
