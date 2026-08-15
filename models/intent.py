from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class Action(str, Enum):
    BORROW_AGAINST = "borrow_against"
    TRADE = "trade"
    REDEEM = "redeem"


class Intent(BaseModel):
    """The versioned request envelope sent by an agent."""

    model_config = ConfigDict(extra="forbid")

    envelope_version: str = Field(pattern=r"^custos/1$")
    agent_id: str = Field(min_length=1)
    action: Action
    asset_id: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^USD$")
    issued_at: datetime
    expires_at: datetime
    downstream: AnyHttpUrl | None = None
