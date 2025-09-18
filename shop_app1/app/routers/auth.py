from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.user import User
from app.utils.security import verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# форма логина
@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

# обработка логина
@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {"request": request, "error": "Неверный логин или пароль"})

    # сохраняем в сессии
    request.session["user_id"] = user.id
    request.session["is_admin"] = user.is_admin

    return RedirectResponse("/admin", status_code=303)

# выход
@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
