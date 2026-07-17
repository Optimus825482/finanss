import os
import secrets
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

PUBLIC_PATHS = ("/api/status", "/docs", "/openapi.json", "/redoc")
DESTRUCTIVE_PREFIXES = ("/api/admin/reset",)


def _safe_compare(a: str, b: str) -> bool:
    """Length-safe constant-time compare (compare_digest requires equal length)."""
    if not a or not b or len(a) != len(b):
        return False
    return secrets.compare_digest(a, b)


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Per-request read so env changes take effect without reload.
        api_key = os.getenv("API_KEY", "")
        if api_key:
            if request.method == "OPTIONS":
                return await call_next(request)
            if any(request.url.path.startswith(p) for p in PUBLIC_PATHS):
                return await call_next(request)
            auth = request.headers.get("X-API-Key", "")
            if not _safe_compare(auth, api_key):
                raise HTTPException(status_code=401, detail="Unauthorized")

        # Destructive admin reset: just ask for confirmation header.
        path = request.url.path
        if any(path.startswith(p) for p in DESTRUCTIVE_PREFIXES) and request.method == "POST":
            if request.headers.get("X-Confirm-Reset", "").lower() != "yes":
                raise HTTPException(
                    status_code=400,
                    detail="Emin misin? X-Confirm-Reset: yes header'ı ekle.",
                )
        return await call_next(request)
