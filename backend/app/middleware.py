import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

API_KEY = os.getenv("API_KEY", "")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if API_KEY:
            if request.method == "OPTIONS":
                return await call_next(request)
            public_paths = ["/api/status", "/docs", "/openapi.json", "/redoc"]
            if any(request.url.path.startswith(p) for p in public_paths):
                return await call_next(request)
            auth = request.headers.get("X-API-Key", "")
            if auth != API_KEY:
                raise HTTPException(status_code=401, detail="Unauthorized")
        return await call_next(request)
