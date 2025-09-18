from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin")

@router.get("/", response_class=HTMLResponse)
def admin_index(request: Request):
    return templates.TemplateResponse("admin/index.html", {"request": request})
