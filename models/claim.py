from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Claim(BaseModel):
    """Seeded representation of the asset state currently asserted on-chain."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str
    issuer: str
    underlying_tenor: str
    claimed_nav_per_token: Decimal = Field(gt=0)
    claimed_backing_usd: Decimal = Field(ge=0)
    tokens_outstanding: Decimal = Field(gt=0)
    claimed_yield_bps: int = Field(ge=0)
    last_attested_at: datetime
    chain: str
    contract_address: str
