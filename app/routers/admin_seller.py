from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Seller  # 🆕 модель продавца
from app.services.audit import write_audit, get_actor

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
    request: Request,
    name: str = Form(...),
    city: str = Form(None),
    db: Session = Depends(get_db),
):
    # 🆕 Получаем текущего пользователя для общего аудита
    actor = get_actor(request, db)

    seller = Seller(name=name, city=city)
    db.add(seller)
    db.commit()
    db.refresh(seller)

    # 🆕 Пишем общий аудит создания продавца
    write_audit(
        db=db,
        entity_type="seller",
        entity_id=seller.id,
        action="seller_created",
        actor=actor,
        old_data=None,
        new_data={
            "id": seller.id,
            "name": seller.name,
            "city": seller.city,
        },
        note="Создан новый продавец",
    )

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
    request: Request,
    seller_id: int,
    name: str = Form(...),
    city: str = Form(None),
    db: Session = Depends(get_db),
):
    seller = db.query(Seller).get(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Продавец не найден")

    # 🆕 Получаем текущего пользователя для общего аудита
    actor = get_actor(request, db)

    # 🆕 Сохраняем старое состояние до изменения
    old_data = {
        "id": seller.id,
        "name": seller.name,
        "city": seller.city,
    }

    seller.name = name
    seller.city = city

    # 🆕 Формируем новое состояние после изменения
    new_data = {
        "id": seller.id,
        "name": seller.name,
        "city": seller.city,
    }

    # 🆕 Пишем общий аудит обновления продавца
    write_audit(
        db=db,
        entity_type="seller",
        entity_id=seller.id,
        action="seller_updated",
        actor=actor,
        old_data=old_data,
        new_data=new_data,
        note="Обновление продавца",
    )

    db.commit()
    return RedirectResponse("/admin/sellers", status_code=303)


# 🗑 удаление
@router.post("/{seller_id}/delete")
def seller_delete(request: Request, seller_id: int, db: Session = Depends(get_db)):
    seller = db.query(Seller).get(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Продавец не найден")

    # 🆕 Получаем текущего пользователя для общего аудита
    actor = get_actor(request, db)

    # 🆕 Сохраняем старое состояние до удаления
    old_data = {
        "id": seller.id,
        "name": seller.name,
        "city": seller.city,
    }

    db.delete(seller)

    # 🆕 Пишем общий аудит удаления продавца
    write_audit(
        db=db,
        entity_type="seller",
        entity_id=seller_id,
        action="seller_deleted",
        actor=actor,
        old_data=old_data,
        new_data=None,
        note="Удален продавец",
    )

    db.commit()
    return RedirectResponse("/admin/sellers", status_code=303)