from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WatchlistItemIn(BaseModel):
    ticker: str
    notes: Optional[str] = None


class WatchlistItemOut(BaseModel):
    id: int
    ticker: str
    notes: Optional[str] = None
    added_at: datetime
    price: Optional[float] = None
    change_pct: Optional[float] = None

    class Config:
        from_attributes = True
