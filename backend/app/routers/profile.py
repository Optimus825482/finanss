from fastapi import APIRouter

from app.database import SessionLocal  # TODO: use Depends(get_db)
from app.schemas import ProfileOut, ProfileUpdateIn
from app.services.memory_service import get_or_create_profile, update_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def api_get_profile():
    db = SessionLocal()
    try:
        return get_or_create_profile(db)
    finally:
        db.close()


@router.put("", response_model=ProfileOut)
def api_update_profile(body: ProfileUpdateIn):
    db = SessionLocal()
    try:
        kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
        return update_profile(db, **kwargs)
    finally:
        db.close()
