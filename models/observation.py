from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class Observation(BaseModel):
    source: str
    dataset: str = "daily_treasury_yield_curve"
    tenor: str
    observed_yield_bps: int
    record_date: date
    fetched_at: datetime
    cache_hit: bool = False
