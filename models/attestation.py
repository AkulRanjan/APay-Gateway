from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel


class Scores(BaseModel):
    staleness_hours: float | None = None
    staleness_threshold_hours: float | None = None
    yield_drift: float | None = None
    yield_drift_threshold: float | None = None
    backing_ratio: float | None = None
    backing_ratio_floor: float | None = None


class Attestation(BaseModel):
    attestation_id: str
    verdict: Literal["ALLOW"] = "ALLOW"
    asset_id: str
    agent_id: str
    action: str
    amount: Decimal
    scores: Scores
    reference: dict[str, Any]
    issued_at: datetime
    expires_at: datetime
    signature: str | None = None
    public_key: str | None = None
    signature_alg: str = "Ed25519"
    canonicalization: str = "JCS/RFC8785-lite"


class BlockResponse(BaseModel):
    verdict: Literal["BLOCK"] = "BLOCK"
    error: str
    error_name: str
    detail: str
    asset_id: str | None = None
    scores: Scores | None = None
    reference: dict[str, Any] | None = None
    issued_at: datetime
