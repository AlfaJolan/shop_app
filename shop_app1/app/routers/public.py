from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.catalog import Category, Product

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    db: Session = Depends(get_db),
    q: Optional[str] = None
):
    # Категории (для меню/фильтров)
    categories = db.query(Category).order_by(Category.name).all()

    # Товары + подгружаем варианты
    query = (
        db.query(Product)
        .options(selectinload(Product.variants))
        .filter(Product.is_active == True)
        .order_by(Product.name)
    )
    if q:
        like = f"%{q}%"
        query = query.filter(Product.name.ilike(like))
    products = query.all()

    # Flash-сообщение из сессии (после /cart/add и др.)
    flash = request.session.get("flash") or ""
    if "flash" in request.session:
        del request.session["flash"]

    # Счётчик корзины в шапке (сумма qty по всем позициям)
    cart = request.session.get("cart") or {}
    try:
        cart_count = sum(int(item.get("qty", 0)) for item in cart.values())
    except Exception:
        cart_count = 0

    return templates.TemplateResponse(
        "public/index.html",
        {
            "request": request,
            "categories": categories,
            "products": products,
            "q": q or "",
            "flash": flash,
            "cart_count": cart_count,  # ← добавили
        },
    )
