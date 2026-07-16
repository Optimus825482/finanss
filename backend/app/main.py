import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from app.database import init_db
from app.middleware import APIKeyMiddleware
from app.scheduler import start_scheduler
from app.services.admin_service import seed_default_provider
from app.routers import register_routers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown lifecycle."""
    init_db()
    seed_default_provider()
    start_scheduler()

    # Sanal bakiyeyi baslat (yoksa 100k USD ile olusur)
    from app.database import SessionLocal
    from app.services.balance_service import get_balance
    db = SessionLocal()
    try:
        bal = get_balance(db)
        db.commit()
        logger.info("Sanal bakiye hazir: $%.2f", bal.cash)
    except Exception as e:
        logger.warning("Bakiye baslatilamadi: %s", e)
    finally:
        db.close()

    yield


app = FastAPI(title="ORBIS FINAI - ORBIS Finance Analyze Team API", lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3009", "https://finans.erkanerdem.online"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(APIKeyMiddleware)


register_routers(app)
