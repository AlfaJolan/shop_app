from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.user import User
from app.utils.enums import UserRole
from app.utils.security import hash_password

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# список пользователей
@router.get("")
def list_users(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).all()
    return templates.TemplateResponse(
        "admin/users/list.html", {"request": request, "users": users}
    )


# форма создания
@router.get("/create")
def create_user_form(request: Request):
    return templates.TemplateResponse(
        "admin/users/create.html",
        {"request": request, "roles": [r.value for r in UserRole]},
    )


# обработка создания
@router.post("/create")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    # проверка на уникальность
    exists = db.query(User).filter(User.username == username).first()
    if exists:
        return templates.TemplateResponse(
            "admin/users/create.html",
            {
                "request": request,
                "roles": [r.value for r in UserRole],
                "error": "Пользователь с таким именем уже существует",
            },
        )

    user = User(username=username, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["flash"] = f"✅ Пользователь {username} создан с ролью {role}"
    return RedirectResponse("/admin/users", status_code=303)

# форма редактирования
@router.get("/{user_id}/edit")
def edit_user_form(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        return RedirectResponse("/admin/users", status_code=303)

    return templates.TemplateResponse(
        "admin/users/edit.html",
        {
            "request": request,
            "user": user,
            "roles": [r.value for r in UserRole],
        },
    )


# обработка редактирования
@router.post("/{user_id}/edit")
def edit_user(
    user_id: int,
    request: Request,
    username: str = Form(...),
    password: str = Form(""),  # необязательное поле
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).get(user_id)
    if not user:
        return RedirectResponse("/admin/users", status_code=303)

    # проверка на уникальность username
    exists = db.query(User).filter(User.username == username, User.id != user_id).first()
    if exists:
        return templates.TemplateResponse(
            "admin/users/edit.html",
            {
                "request": request,
                "user": user,
                "roles": [r.value for r in UserRole],
                "error": "Пользователь с таким именем уже существует",
            },
        )

    user.username = username
    user.role = role
    if password.strip():
        user.password_hash = hash_password(password)

    db.commit()
    request.session["flash"] = f"✅ Пользователь {username} обновлён"
    return RedirectResponse("/admin/users", status_code=303)
