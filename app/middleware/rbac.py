from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from fastapi import Request
from app.utils.enums import UserRole


ACCESS_MATRIX = {
    UserRole.ADMIN.value: ["*"],  # полный доступ
    UserRole.SELLER.value: [
        "/admin/dashboard",
        "/admin/products",
        "/admin/invoices",
    ],
    UserRole.PICKER.value: [
        "/admin/dashboard",
        "/admin/orders/live",
    ],
}


class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Проверяем только разделы админки (кроме логина/логаута)
        if path.startswith("/admin") and path not in ["/login", "/logout"]:
            role = (request.session.get("role") or "").strip().lower()

            if not role:
                return RedirectResponse("/login")

            # 🔹 если админ → полный доступ
            if role == UserRole.ADMIN.value:
                return await call_next(request)

            # 🔹 если у роли есть доступ
            allowed_paths = ACCESS_MATRIX.get(role, [])
            if "*" in allowed_paths or any(path.startswith(p) for p in allowed_paths):
                return await call_next(request)

            # ❌ иначе → отдаём 403 вместо редиректа на referer
            return JSONResponse(
                {"error": "У вас нет прав для доступа к этой странице."},
                status_code=403,
            )

        return await call_next(request)
