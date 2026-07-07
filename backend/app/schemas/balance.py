from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BalanceOut(BaseModel):
    cash: float
    updated_at: datetime

    class Config:
        from_attributes = True


class BalanceTxOut(BaseModel):
    id: int
    type: str
    amount: float
    note: Optional[str] = None
    position_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BalanceDepositIn(BaseModel):
    amount: float
    note: Optional[str] = None
