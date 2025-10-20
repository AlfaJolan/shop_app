from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.salesperson import Salesperson
from app.models.catalog import Seller

router = APIRouter(prefix="/admin/salespersons", tags=["admin-salespersons"])
templates = Jinja2Templates(directory="app/templates")


# ==== DB ====
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==== LIST ====
@router.get("/")
def salespersons_index(request: Request, db: Session = Depends(get_db)):
    salespersons = db.query(Salesperson).all()
    sellers = db.query(Seller).all()
    return templates.TemplateResponse("admin/salespersons.html", {
        "request": request,
        "salespersons": salespersons,
        "sellers": sellers,
    })


# ==== CREATE ====
@router.post("/create")
def salespersons_create(
    name: str = Form(...),
    phone: str = Form(""),
    seller_id: int = Form(...),
    db: Session = Depends(get_db),
):
    seller = db.query(Seller).get(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Магазин не найден")

    sp = Salesperson(name=name, phone=phone, seller_id=seller_id)
    db.add(sp)
    db.commit()
    return RedirectResponse("/admin/salespersons", status_code=303)


# ==== DELETE ====
@router.post("/delete")
def salespersons_delete(id: int = Form(...), db: Session = Depends(get_db)):
    salesperson = db.query(Salesperson).get(id)
    if not salesperson:
        raise HTTPException(status_code=404, detail="Продавец не найден")

    db.delete(salesperson)
    db.commit()
    return RedirectResponse("/admin/salespersons", status_code=303)
