# app/routers/admin_catalog.py
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db import get_db
from app.models.catalog import Category

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin/catalog", tags=["admin-catalog"])


# --- utils ---

CYR_TO_LAT = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y",
    "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
    "х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ы":"y","э":"e","ю":"yu","я":"ya",
    "ъ":"","ь":""
}
def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in " _-./":
            out.append("-")
        else:
            out.append(CYR_TO_LAT.get(ch, ""))
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "cat"

def _unique_slug(db: Session, base: str, current_id: Optional[int] = None) -> str:
    base = _slugify(base)
    slug = base
    i = 2
    while True:
        q = db.query(Category).filter(Category.slug == slug)
        if current_id:
            q = q.filter(Category.id != current_id)
        exists = db.query(q.exists()).scalar()
        if not exists:
            return slug
        slug = f"{base}-{i}"
        i += 1


# --- Категории ---

@router.get("/categories", response_class=HTMLResponse)
def category_list(
    request: Request,
    db: Session = Depends(get_db),
    q: Optional[str] = None,
):
    query = db.query(Category).order_by(Category.name.asc())
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Category.name.ilike(like), Category.slug.ilike(like)))
    cats = query.all()
    return templates.TemplateResponse("admin/category_list.html", {
        "request": request,
        "categories": cats,
        "q": q or "",
    })


@router.get("/categories/new", response_class=HTMLResponse)
def category_new_form(request: Request):
    return templates.TemplateResponse("admin/category_form.html", {
        "request": request,
        "mode": "new",
        "cat": None,
    })


@router.post("/categories/new")
def category_new(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    slug: Optional[str] = Form(""),
):
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Название обязательно")
    if not slug:
        slug = name

    slug = _unique_slug(db, slug)
    cat = Category(name=name, slug=slug)
    db.add(cat)
    db.commit()
    return RedirectResponse(url="/admin/catalog/categories", status_code=303)


@router.get("/categories/{cat_id}/edit", response_class=HTMLResponse)
def category_edit_form(request: Request, cat_id: int, db: Session = Depends(get_db)):
    cat = db.query(Category).get(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return templates.TemplateResponse("admin/category_form.html", {
        "request": request,
        "mode": "edit",
        "cat": cat,
    })


@router.post("/categories/{cat_id}/edit")
def category_edit(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    name: str = Form(...),
    slug: Optional[str] = Form(""),
):
    cat = db.query(Category).get(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Название обязательно")

    if slug:
        new_slug = _unique_slug(db, slug, current_id=cat.id)
    else:
        new_slug = _unique_slug(db, name, current_id=cat.id)

    cat.name = name
    cat.slug = new_slug
    db.commit()
    return RedirectResponse(url="/admin/catalog/categories", status_code=303)


@router.post("/categories/{cat_id}/delete")
def category_delete(cat_id: int, db: Session = Depends(get_db)):
    cat = db.query(Category).get(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    # безопасное удаление: если есть товары — не даём удалить
    prod_count = db.execute(
        "SELECT COUNT(1) FROM products WHERE category_id = :cid",
        {"cid": cat.id}
    ).scalar() or 0
    if prod_count:
        raise HTTPException(status_code=400, detail="Нельзя удалить: есть товары в категории")

    db.delete(cat)
    db.commit()
    return RedirectResponse(url="/admin/catalog/categories", status_code=303)
