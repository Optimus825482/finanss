from typing import Optional

from pydantic import BaseModel


class ProfileOut(BaseModel):
    id: int
    display_name: str
    risk_tolerance: str
    investment_style: str
    preferred_markets: list[str]
    preferred_sectors: list[str]
    language: str

    class Config:
        from_attributes = True


class ProfileUpdateIn(BaseModel):
    display_name: Optional[str] = None
    risk_tolerance: Optional[str] = None
    investment_style: Optional[str] = None
    preferred_markets: Optional[list[str]] = None
    preferred_sectors: Optional[list[str]] = None
    language: Optional[str] = None
