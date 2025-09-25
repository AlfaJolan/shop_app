from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Product
# ⚡ тут тебе ProductImage, ProductVideo тоже пригодятся, если будешь показывать

router = APIRouter(prefix="/products", tags=["products"])   # 🔹 префикс изменён
templates = Jinja2Templates(directory="app/templates")


# ---- DB ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 🔹 публичная страница товара
@router.get("/{product_id}")
def product_detail(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return templates.TemplateResponse("public/product_detail.html", {
        "request": request,
        "product": product,
    })
