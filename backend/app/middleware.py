import os
import secrets
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

PUBLIC_PATHS = ("/api/status", "/docs", "/openapi.json", "/redoc")


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
            # Constant-time compare to avoid timing side-channel.
            if not secrets.compare_digest(auth, api_key):
                raise HTTPException(status_code=401, detail="Unauthorized")
        return await call_next(request)
