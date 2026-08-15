from __future__ import annotations

from datetime import datetime, timedelta, timezone

from attest.errors import ERRORS
from models import BlockResponse, Intent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_temporal_envelope(intent: Intent) -> BlockResponse | None:
    """Return a structured error for valid schema with invalid clock semantics."""
    if intent.issued_at.tzinfo is None or intent.expires_at.tzinfo is None:
        error = ERRORS["CUSTOS-E100"]
        return BlockResponse(error=error.code, error_name=error.name,
                             detail="issued_at and expires_at must include a UTC offset.", issued_at=utc_now())
    now = utc_now()
    if intent.expires_at.astimezone(timezone.utc) <= now:
        error = ERRORS["CUSTOS-E102"]
        return BlockResponse(error=error.code, error_name=error.name,
                             detail="expires_at must be in the future.", asset_id=intent.asset_id, issued_at=now)
    if intent.issued_at.astimezone(timezone.utc) > now + timedelta(minutes=5):
        error = ERRORS["CUSTOS-E103"]
        return BlockResponse(error=error.code, error_name=error.name,
                             detail="issued_at is more than five minutes in the future.", asset_id=intent.asset_id, issued_at=now)
    return None
