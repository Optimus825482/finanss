from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.scheduler import start_scheduler
from app.services.admin_service import seed_default_provider
from app.routers import register_routers

app = FastAPI(title="ORBIS FINAI - ORBIS Finance Analyze Team API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3009", "https://finans.erkanerdem.online"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    seed_default_provider()
    start_scheduler()


register_routers(app)
