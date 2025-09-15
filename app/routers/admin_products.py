from fastapi import APIRouter, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Product, Category, Variant
from pathlib import Path
import shutil, uuid, os

router = APIRouter(prefix="/admin/catalog/products", tags=["admin-products"])
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = Path("app/static/uploads/products")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---- DB ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 📦 список товаров
@router.get("/")
def products_index(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return templates.TemplateResponse("admin/products_index.html", {
        "request": request,
        "products": products,
    })


# 🆕 форма создания
@router.get("/new")
def product_new(request: Request, db: Session = Depends(get_db)):
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
    image: UploadFile = File(None),

    new_name: list[str] = Form([]),
    new_price: list[float] = Form([]),
    new_stock: list[int] = Form([]),

    db: Session = Depends(get_db),
):
    # ---- картинка с UUID ----
    filename = None
    if image and image.filename:
        ext = Path(image.filename).suffix
        filename = f"{uuid.uuid4().hex}{ext}"
        with open(UPLOAD_DIR / filename, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    product = Product(
        name=name, sku=sku, category_id=category_id,
        unit=unit, image=filename
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # новые варианты
    for i in range(len(new_name)):
        if not new_name[i]:
            continue
        v = Variant(
            product_id=product.id,
            name=new_name[i],
            unit_price=new_price[i],
            stock=new_stock[i],
        )
        db.add(v)

    db.commit()
    return RedirectResponse("/admin/catalog/products", status_code=303)



# ✏️ форма редактирования
@router.get("/{product_id}/edit")
def product_edit(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    categories = db.query(Category).all()
    return templates.TemplateResponse("admin/product_form.html", {
        "request": request,
        "product": product,
        "categories": categories,
        "variants": product.variants,
    })


# 🔄 обновление товара
@router.post("/{product_id}/update")
def product_update(
    product_id: int,
    name: str = Form(...),
    sku: str = Form(None),
    category_id: int = Form(None),
    unit: str = Form("шт"),
    image: UploadFile = File(None),

    var_id: list[int] = Form([]),
    var_name: list[str] = Form([]),
    var_price: list[float] = Form([]),
    var_stock: list[int] = Form([]),

    new_name: list[str] = Form([]),
    new_price: list[float] = Form([]),
    new_stock: list[int] = Form([]),

    delete_variant_id: list[int] = Form([]),

    db: Session = Depends(get_db),
):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    # ---- новая картинка ----
    if image and image.filename:
        ext = Path(image.filename).suffix
        new_filename = f"{uuid.uuid4().hex}{ext}"
        with open(UPLOAD_DIR / new_filename, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # удалить старую картинку
        if product.image:
            try:
                os.remove(UPLOAD_DIR / product.image)
            except Exception:
                pass

        product.image = new_filename

    # обновляем товар
    product.name = name
    product.sku = sku
    product.category_id = category_id
    product.unit = unit

    # существующие варианты
    for i in range(len(var_id)):
        vid = var_id[i]
        v = db.query(Variant).get(vid)
        if not v:
            continue
        if vid in delete_variant_id:
            db.delete(v)
            continue
        v.name = var_name[i]
        v.unit_price = var_price[i]
        v.stock = var_stock[i]

    # новые варианты
    for i in range(len(new_name)):
        if not new_name[i]:
            continue
        v = Variant(
            product_id=product.id,
            name=new_name[i],
            unit_price=new_price[i],
            stock=new_stock[i],
        )
        db.add(v)

    db.commit()
    return RedirectResponse(f"/admin/catalog/products/{product.id}/edit", status_code=303)
