from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ProfileOut, ProfileUpdateIn
from app.services.memory_service import get_or_create_profile, update_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def api_get_profile(db: Session = Depends(get_db)):
    return get_or_create_profile(db)


@router.put("", response_model=ProfileOut)
def api_update_profile(body: ProfileUpdateIn, db: Session = Depends(get_db)):
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    return update_profile(db, **kwargs)
