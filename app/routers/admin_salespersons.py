from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.salesperson import Salesperson
from app.models.catalog import Seller
from app.services.audit import write_audit, get_actor

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
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    seller_id: int = Form(...),
    db: Session = Depends(get_db),
):
    seller = db.query(Seller).get(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Магазин не найден")

    # 🆕 Получаем текущего пользователя для общего аудита
    actor = get_actor(request, db)

    sp = Salesperson(name=name, phone=phone, seller_id=seller_id)
    db.add(sp)
    db.commit()
    db.refresh(sp)

    # 🆕 Пишем общий аудит создания продавца
    write_audit(
        db=db,
        entity_type="salesperson",
        entity_id=sp.id,
        action="salesperson_created",
        actor=actor,
        old_data=None,
        new_data={
            "id": sp.id,
            "name": sp.name,
            "phone": sp.phone,
            "seller_id": sp.seller_id,
            "seller_name": seller.name,
        },
        note="Создан новый продавец",
    )

    db.commit()
    return RedirectResponse("/admin/salespersons", status_code=303)


# ==== DELETE ====
@router.post("/delete")
def salespersons_delete(request: Request, id: int = Form(...), db: Session = Depends(get_db)):
    salesperson = db.query(Salesperson).get(id)
    if not salesperson:
        raise HTTPException(status_code=404, detail="Продавец не найден")

    # 🆕 Получаем текущего пользователя для общего аудита
    actor = get_actor(request, db)

    # 🆕 Сохраняем старое состояние до удаления
    old_data = {
        "id": salesperson.id,
        "name": salesperson.name,
        "phone": salesperson.phone,
        "seller_id": salesperson.seller_id,
        "seller_name": salesperson.seller.name if getattr(salesperson, "seller", None) else None,
    }

    db.delete(salesperson)

    # 🆕 Пишем общий аудит удаления продавца
    write_audit(
        db=db,
        entity_type="salesperson",
        entity_id=id,
        action="salesperson_deleted",
        actor=actor,
        old_data=old_data,
        new_data=None,
        note="Удален продавец",
    )

    db.commit()
    return RedirectResponse("/admin/salespersons", status_code=303)