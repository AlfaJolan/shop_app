from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Seller  # 🆕 модель продавца

router = APIRouter(prefix="/admin/sellers", tags=["admin-sellers"])
templates = Jinja2Templates(directory="app/templates")


# ---- DB ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 📦 список продавцов
@router.get("/")
def sellers_index(request: Request, db: Session = Depends(get_db)):
    sellers = db.query(Seller).all()
    return templates.TemplateResponse("admin/sellers_index.html", {
        "request": request,
        "sellers": sellers,
    })


# 🆕 форма создания
@router.get("/new")
def seller_new(request: Request):
    return templates.TemplateResponse("admin/seller_form.html", {
        "request": request,
        "seller": None,
    })


# 💾 создание
@router.post("/create")
def seller_create(
    name: str = Form(...),
    city: str = Form(None),
    db: Session = Depends(get_db),
):
    seller = Seller(name=name, city=city)
    db.add(seller)
    db.commit()
    return RedirectResponse("/admin/sellers", status_code=303)


# ✏️ форма редактирования
@router.get("/{seller_id}/edit")
def seller_edit(seller_id: int, request: Request, db: Session = Depends(get_db)):
    seller = db.query(Seller).get(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Продавец не найден")
    return templates.TemplateResponse("admin/seller_form.html", {
        "request": request,
        "seller": seller,
    })


# 🔄 обновление
@router.post("/{seller_id}/update")
def seller_update(
    seller_id: int,
    name: str = Form(...),
    city: str = Form(None),
    db: Session = Depends(get_db),
):
    seller = db.query(Seller).get(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Продавец не найден")

    seller.name = name
    seller.city = city
    db.commit()
    return RedirectResponse("/admin/sellers", status_code=303)


# 🗑 удаление
@router.post("/{seller_id}/delete")
def seller_delete(seller_id: int, db: Session = Depends(get_db)):
    seller = db.query(Seller).get(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Продавец не найден")

    db.delete(seller)
    db.commit()
    return RedirectResponse("/admin/sellers", status_code=303)
