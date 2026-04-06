from fastapi import APIRouter, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Product, Category, Variant, Seller, ProductImage, ProductVideo   # 🆕 добавили ProductImage, ProductVideo
from pathlib import Path
import shutil, uuid, os
from typing import Optional

from app.services.audit import write_audit, get_actor # ✅ добавляем импорт для аудита

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
def extract_youtube_id(url: str) -> str:
    """Вытаскиваем только ID из YouTube URL"""
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]
    if "/shorts/" in url:
        return url.split("/shorts/")[-1].split("?")[0]
    return url  # если уже ID



# 📦 список товаров
@router.get("/")
def products_index(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return templates.TemplateResponse("admin/products_index.html", {
        "request": request,
        "products": products,
    })

# ➕ форма создания нового товара
@router.get("/new")
def product_new(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    sellers = db.query(Seller).order_by(Seller.id.asc()).all()

    # Категория по умолчанию = "Посуда"
    default_category = (
        db.query(Category)
        .filter(Category.name.ilike("Посуда"))
        .first()
    )

    # 🆕 Продавец по умолчанию = первый по ID
    default_seller = (
        db.query(Seller)
        .order_by(Seller.id.asc())
        .first()
    )

    return templates.TemplateResponse("admin/product_form.html", {
        "request": request,
        "categories": categories,
        "sellers": sellers,
        "product": None,
        "default_category_id": default_category.id if default_category else None,
        "default_category_name": default_category.name if default_category else "---",
        "default_seller_id": default_seller.id if default_seller else None,  # 🆕
        "default_seller_name": (
            f"{default_seller.name} ({default_seller.city})"
            if default_seller and default_seller.city
            else (default_seller.name if default_seller else "---")
        ),  # 🆕
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
    description: str = Form(None),   # 🆕 описание
    image: UploadFile = File(None),
    gallery: list[UploadFile] = File([]),   # 🆕 дополнительные фото
    new_video_url: list[str] = Form([]),    # 🆕 новые видео ссылки
    new_video_title: list[str] = Form([]),  # 🆕 подписи к видео

    new_name: list[str] = Form([]),
    new_price_net_cost: list[float] = Form([]),
    new_price: list[float] = Form([]),
    # 🆕 новые поля для логики "штуки и коробки"
    new_pieces: list[int] = Form([]),
    new_boxes: list[int] = Form([]),

    db: Session = Depends(get_db),
):
    # 🆕 Получаем текущего пользователя для общего аудита
    actor = get_actor(request, db)

    # ---- картинка с UUID ----
    filename = None
    if image and image.filename:
        ext = Path(image.filename).suffix
        filename = f"{uuid.uuid4().hex}{ext}"
        with open(UPLOAD_DIR / filename, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    # 🆕 теперь сохраняем seller_id и description
    product = Product(
        name=name,
        sku=None,  # 🆕 сначала создаём без SKU (будет сгенерирован после commit)
        category_id=category_id,
        unit=unit,
        image=filename,
        seller_id=seller_id,
        description=description
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # 🆕 === АВТОГЕНЕРАЦИЯ SKU ===
    # если SKU не передан вручную → генерируем из ID
    if not sku or not sku.strip():
        # простой вариант
        product.sku = str(product.id)

        # 🔥 если хочешь красивый формат — раскомментируй:
        product.sku = f"SKU-{product.id:06d}"
    else:
        # если пользователь ввёл SKU вручную — используем его
        product.sku = sku.strip()

    db.commit()
    db.refresh(product)

    # 🆕 создаём папку для галереи
    gallery_dir = UPLOAD_DIR / str(product.id) / "gallery"
    gallery_dir.mkdir(parents=True, exist_ok=True)

    # 🆕 Для общего аудита собираем, какие файлы/видео/варианты были созданы
    created_gallery_files = []
    created_videos = []
    created_variants = []

    # 🆕 сохраняем доп. фото
    for file in gallery:
        if file and file.filename:
            ext = Path(file.filename).suffix
            fname = f"{uuid.uuid4().hex}{ext}"
            with open(gallery_dir / fname, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            db.add(ProductImage(product_id=product.id, image_url=fname))

            # 🆕 запоминаем фото для audit_log
            created_gallery_files.append(fname)

    # 🆕 сохраняем видео ссылки
    for i, url in enumerate(new_video_url):
        if not url:
            continue
        title = new_video_title[i] if i < len(new_video_title) else None
        video_id = extract_youtube_id(url)
        db.add(ProductVideo(product_id=product.id, video_url=video_id, title=title, sort_order=i))

        # 🆕 запоминаем видео для audit_log
        created_videos.append({
            "video_url": video_id,
            "title": title,
            "sort_order": i,
        })

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

        # 🆕 запоминаем вариант для audit_log
        created_variants.append({
            "name": new_name[i],
            "unit_price_net_cost": float(new_price_net_cost[i]) if i < len(new_price_net_cost) else 0.0,
            "unit_price": float(new_price[i]) if i < len(new_price) else 0.0,
            "stock": int(stock),
        })

    # 🆕 Пишем общий аудит создания товара.
    # old_data = None, потому что товара раньше не существовало.
    write_audit(
        db=db,
        entity_type="product",
        entity_id=product.id,
        action="product_created",
        actor=actor,
        old_data=None,
        new_data={
            "product": {
                "id": product.id,
                "name": product.name,
                "sku": product.sku,  # 🆕 уже сгенерированный SKU попадёт в аудит
                "category_id": product.category_id,
                "unit": product.unit,
                "seller_id": product.seller_id,
                "description": product.description,
                "image": product.image,
            },
            "gallery_count": len(created_gallery_files),
            "gallery_files": created_gallery_files,
            "videos_count": len(created_videos),
            "videos": created_videos,
            "variants_count": len(created_variants),
            "variants": created_variants,
        },
        note="Создан новый товар",
    )

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
    request: Request,  # 🆕 добавили request для получения пользователя
    product_id: int,
    name: str = Form(...),
    sku: str = Form(None),
    category_id: int = Form(None),
    unit: str = Form("шт"),
    seller_id: int = Form(...),   # 🆕 поле продавца
    description: str = Form(None),   # 🆕 описание
    image: UploadFile = File(None),
    gallery: list[UploadFile] = File([]),   # 🆕 дополнительные фото
    delete_image_id: list[int] = Form([]),  # 🆕 удаление фото
    video_url: list[str] = Form([]),        # 🆕 существующие видео
    video_title: list[str] = Form([]),      # 🆕 подписи для существующих
    video_id: list[int] = Form([]),         # 🆕 id существующих видео
    delete_video_id: list[int] = Form([]),  # 🆕 удаление видео
    new_video_url: list[str] = Form([]),    # 🆕 новые ссылки
    new_video_title: list[str] = Form([]),  # 🆕 подписи к новым

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

    # 🆕 текущий пользователь
    actor = get_actor(request, db)

    # 🆕 OLD SNAPSHOT (до изменений)
    old_product = {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "category_id": product.category_id,
        "seller_id": product.seller_id,
        "unit": product.unit,
        "description": product.description,
        "image": product.image,
    }

    old_variants = []
    for v in product.variants:
        old_variants.append({
            "id": v.id,
            "name": v.name,
            "unit_price_net_cost": float(v.unit_price_net_cost or 0),
            "unit_price": float(v.unit_price or 0),
            "stock": int(v.stock or 0),
        })

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

    # 🆕 описание
    product.description = description
    # 🆕 обновляем продавца
    product.seller_id = seller_id
    # обновляем товар
    product.name = name
    product.sku = sku
    product.category_id = category_id
    product.unit = unit

    # 🆕 создаём папку для галереи
    gallery_dir = UPLOAD_DIR / str(product.id) / "gallery"
    gallery_dir.mkdir(parents=True, exist_ok=True)

    # 🆕 удаляем отмеченные фото
    for img_id in delete_image_id:
        img = db.query(ProductImage).get(img_id)
        if img:
            try:
                os.remove(gallery_dir / img.image_url)
            except Exception:
                pass
            db.delete(img)

    # 🆕 сохраняем новые фото
    for file in gallery:
        if file and file.filename:
            ext = Path(file.filename).suffix
            fname = f"{uuid.uuid4().hex}{ext}"
            with open(gallery_dir / fname, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            db.add(ProductImage(product_id=product.id, image_url=fname))

    # 🆕 удаляем отмеченные видео
    for vid in delete_video_id:
        v = db.query(ProductVideo).get(vid)
        if v:
            db.delete(v)

    # 🆕 обновляем существующие видео (по id)
    for i, vid in enumerate(video_id):
        v = db.query(ProductVideo).get(vid)
        if v:
            v.video_url = video_url[i] if i < len(video_url) else v.video_url
            v.title = video_title[i] if i < len(video_title) else v.title

    # 🆕 новые видео
    for i, url in enumerate(new_video_url):
        if not url:
            continue
        title = new_video_title[i] if i < len(new_video_title) else None
        db.add(ProductVideo(product_id=product.id, video_url= extract_youtube_id(url), title=title, sort_order=i))

    # --- ниже идёт оригинальная логика обновления вариантов ---
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

    # 🆕 NEW SNAPSHOT (после изменений)
    new_product = {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "category_id": product.category_id,
        "seller_id": product.seller_id,
        "unit": product.unit,
        "description": product.description,
        "image": product.image,
    }

    new_variants = []
    for v in product.variants:
        new_variants.append({
            "id": v.id,
            "name": v.name,
            "unit_price_net_cost": float(v.unit_price_net_cost or 0),
            "unit_price": float(v.unit_price or 0),
            "stock": int(v.stock or 0),
        })

    # 🆕 общий аудит обновления товара
    write_audit(
        db=db,
        entity_type="product",
        entity_id=product.id,
        action="product_updated",
        actor=actor,
        old_data={
            "product": old_product,
            "variants": old_variants,
        },
        new_data={
            "product": new_product,
            "variants": new_variants,
        },
        note="Обновление товара",
    )

    db.commit()
    return RedirectResponse(f"/admin/catalog/products/{product.id}/edit", status_code=303)

# 🗃️ архивирование товара (мягкое удаление)
@router.post("/{product_id}/archive")
def product_archive(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    # 🆕 Получаем текущего пользователя для аудита
    actor = get_actor(request, db)

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Если уже архивный — просто возвращаем назад
    if not product.is_active:
        return RedirectResponse("/admin/catalog/products?archived=already", status_code=303)

    old_data = {
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "is_active": product.is_active,
        },
        "variants": [
            {
                "id": v.id,
                "name": v.name,
                "stock": v.stock,
                "is_active": v.is_active,
            }
            for v in product.variants
        ],
    }

    # 🔹 Сам товар архивируем
    product.is_active = False

    # 🔹 Все варианты тоже архивируем и обнуляем остатки
    archived_variants = []
    for v in product.variants:
        archived_variants.append({
            "id": v.id,
            "name": v.name,
            "stock_before": v.stock,
            "is_active_before": v.is_active,
        })

        v.is_active = False
        v.stock = 0

    new_data = {
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "is_active": product.is_active,
        },
        "variants": [
            {
                "id": v.id,
                "name": v.name,
                "stock": v.stock,
                "is_active": v.is_active,
            }
            for v in product.variants
        ],
    }

    write_audit(
        db=db,
        entity_type="product",
        entity_id=product.id,
        action="product_archived",
        actor=actor,
        old_data=old_data,
        new_data=new_data,
        note="Товар архивирован (мягкое удаление)",
    )

    db.commit()

    return RedirectResponse("/admin/catalog/products?archived=1", status_code=303)