from fastapi import APIRouter, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Product, Category, Variant, Seller   # 🆕 добавлен Seller
from pathlib import Path
import shutil, uuid, os
from typing import Optional

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

def safe_int(val: str) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0



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
    sellers = db.query(Seller).all()  # 🆕 добавили выбор продавца
    return templates.TemplateResponse("admin/product_form.html", {
        "request": request,
        "categories": categories,
        "sellers": sellers,           # 🆕 передаём в шаблон
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
    seller_id: int = Form(...),   # 🆕 добавлено поле продавца
    image: UploadFile = File(None),

    new_name: list[str] = Form([]),
    new_price_net_cost: list[float] = Form([]),
    new_price: list[float] = Form([]),
    # 🆕 новые поля для логики "штуки и коробки"
    new_pieces: list[int] = Form([]),
    new_boxes: list[int] = Form([]),

    db: Session = Depends(get_db),
):
    # ---- картинка с UUID ----
    filename = None
    if image and image.filename:
        ext = Path(image.filename).suffix
        filename = f"{uuid.uuid4().hex}{ext}"
        with open(UPLOAD_DIR / filename, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    # 🆕 теперь сохраняем seller_id
    product = Product(
        name=name, sku=sku, category_id=category_id,
        unit=unit, image=filename, seller_id=seller_id
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # новые варианты
    for i in range(len(new_name)):
        if not new_name[i]:
            continue
        pieces = int(new_pieces[i]) if i < len(new_pieces) and new_pieces[i] else 0
        boxes = int(new_boxes[i]) if i < len(new_boxes) and new_boxes[i] else 0
        # 🆕 если коробки > 0 → сохраняем штуки * коробки
        stock = pieces * boxes if boxes > 0 else pieces

        v = Variant(
            product_id=product.id,
            name=new_name[i],
            unit_price_net_cost=new_price_net_cost[i] if i < len(new_price_net_cost) else 0,  # 🆕 безопасно
            unit_price=new_price[i] if i < len(new_price) else 0,
            stock=stock,
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
    sellers = db.query(Seller).all()  # 🆕 список продавцов
    return templates.TemplateResponse("admin/product_form.html", {
        "request": request,
        "product": product,
        "categories": categories,
        "sellers": sellers,           # 🆕 передаём в шаблон
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
    seller_id: int = Form(...),   # 🆕 поле продавца
    image: UploadFile = File(None),

    var_id: list[int] = Form([]),
    var_name: list[str] = Form([]),
    var_net_price: list[float] = Form([]),  # 🆕 себестоимость (unit_price_net_cost)
    var_price: list[float] = Form([]),
    # 🆕 новые поля для логики "штуки и коробки"
    var_pieces: list[int] = Form([]),
    var_boxes: list[int] = Form([]),

    # 🆕 ДОБАВЛЕНИЕ к остатку (появляется при нажатии кнопки)
    var_add_pieces: list[str] = Form([]),
    var_add_boxes: list[str] = Form([]),
    # 🆕

    new_name: list[str] = Form([]),
    new_net_cost_price: list[float] = Form([]),
    new_price: list[float] = Form([]),
    new_pieces: list[int] = Form([]),
    new_boxes: list[int] = Form([]),

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
    product.seller_id = seller_id   # 🆕 обновляем продавца

    # существующие варианты
    for i in range(len(var_id)):
        vid = var_id[i]
        v = db.query(Variant).get(vid)
        if not v:
            continue
        if vid in delete_variant_id:
            db.delete(v)
            continue

        # основная логика из кода (не трогаем):
        pieces = int(var_pieces[i]) if i < len(var_pieces) and var_pieces[i] else 0
        boxes = int(var_boxes[i]) if i < len(var_boxes) and var_boxes[i] else 0
        # 🆕 если коробки > 0 → сохраняем штуки * коробки
        stock = pieces * boxes if boxes > 0 else pieces

        v.name = var_name[i] if i < len(var_name) else v.name
        # 🆕 обновляем себестоимость отдельно
        if i < len(var_net_price):
            v.unit_price_net_cost = var_net_price[i]
        if i < len(var_price):
            v.unit_price = var_price[i]
        v.stock = stock

        # 🆕 ДОБАВИТЬ К ОСТАТКУ: умножаем и прибавляем
        add_pieces = safe_int(var_add_pieces[i]) if i < len(var_add_pieces) else 0
        add_boxes  = safe_int(var_add_boxes[i])  if i < len(var_add_boxes)  else 0
        add_total = add_pieces * add_boxes if add_boxes > 0 else add_pieces
        if add_total:
            v.stock = (v.stock or 0) + add_total

    # новые варианты
    for i in range(len(new_name)):
        if not new_name[i]:
            continue
        pieces = int(new_pieces[i]) if i < len(new_pieces) and new_pieces[i] else 0
        boxes = int(new_boxes[i]) if i < len(new_boxes) and new_boxes[i] else 0
        stock = pieces * boxes if boxes > 0 else pieces

        v = Variant(
            product_id=product.id,
            name=new_name[i],
            unit_price_net_cost = new_net_cost_price[i] if i < len(new_net_cost_price) else 0,
            unit_price=new_price[i] if i < len(new_price) else 0,
            stock=stock,
        )
        db.add(v)

    db.commit()
    return RedirectResponse(f"/admin/catalog/products/{product.id}/edit", status_code=303)
