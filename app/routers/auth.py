import time
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.user import User
from app.utils.security import verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 🔹 Rate limit config
MAX_ATTEMPTS = 5          # максимум попыток
BLOCK_TIME = 60           # блокировка на 60 секунд
login_attempts = {}       # { "ip": {"count": int, "last": timestamp} }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_rate_limit(ip: str) -> bool:
    """Проверка лимита по IP"""
    now = time.time()
    data = login_attempts.get(ip)

    if not data:
        return True

    # если ещё идёт блокировка
    if data["count"] >= MAX_ATTEMPTS and now - data["last"] < BLOCK_TIME:
        return False

    return True


def add_attempt(ip: str):
    """Запись попытки входа"""
    now = time.time()
    if ip not in login_attempts:
        login_attempts[ip] = {"count": 1, "last": now}
    else:
        attempts = login_attempts[ip]
        if now - attempts["last"] > BLOCK_TIME:
            # сбрасываем после блокировки
            login_attempts[ip] = {"count": 1, "last": now}
        else:
            attempts["count"] += 1
            attempts["last"] = now


def reset_attempts(ip: str):
    """Сброс после успешного логина"""
    if ip in login_attempts:
        del login_attempts[ip]


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
    db: Session = Depends(get_db),
):
    client_ip = request.client.host

    # Проверка rate limit
    if not check_rate_limit(client_ip):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Слишком много попыток. Подождите 1 минуту."},
        )

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        add_attempt(client_ip)  # фиксируем неудачную попытку
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Неверный логин или пароль"},
        )

    # Успешный вход — сброс счётчика
    reset_attempts(client_ip)

    # сохраняем в сессии
    request.session["user_id"] = user.id
    role_clean = (user.role or "").strip().lower()
    request.session["role"] = role_clean
    print("🔑 LOGIN SUCCESS:", user.username, "role=", role_clean)




    return RedirectResponse("/admin/dashboard", status_code=303)


# выход
@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
@router.get("/whoami")
def whoami(request: Request):
    return {"user_id": request.session.get("user_id"), "role": request.session.get("role")}

