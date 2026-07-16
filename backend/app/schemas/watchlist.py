from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WatchlistItemIn(BaseModel):
    ticker: str
    notes: Optional[str] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    alert_on_signal: Optional[bool] = True


class WatchlistItemOut(BaseModel):
    id: int
    ticker: str
    notes: Optional[str] = None
    added_at: datetime
    price: Optional[float] = None
    change_pct: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    alert_on_signal: Optional[bool] = True
    last_signal: Optional[str] = None

    class Config:
        from_attributes = True


class WatchlistAlertOut(BaseModel):
    """check_alerts çıktısı — alert tipi + tetiklenmiş durumu."""
    ticker: str
    alert_type: str  # target | stop | signal_change
    current_price: Optional[float] = None
    threshold: Optional[float] = None
    last_signal: Optional[str] = None
    triggered: bool = False

    class Config:
        from_attributes = True
