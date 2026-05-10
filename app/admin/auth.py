import base64

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import settings


class AdminBasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/admin"):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                username, password = decoded.split(":", 1)
                if username == settings.admin_username and password == settings.admin_password:
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            "Доступ запрещён",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="AI Booster Admin"'},
        )