from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CustosError:
    code: str
    name: str
    status_code: int


ERRORS = {
    "CUSTOS-E100": CustosError("CUSTOS-E100", "MALFORMED_ENVELOPE", 400),
    "CUSTOS-E101": CustosError("CUSTOS-E101", "CLAIM_STALE", 403),
    "CUSTOS-E102": CustosError("CUSTOS-E102", "INTENT_EXPIRED", 400),
    "CUSTOS-E103": CustosError("CUSTOS-E103", "CLOCK_SKEW", 400),
    "CUSTOS-E200": CustosError("CUSTOS-E200", "UNKNOWN_ASSET", 404),
    "CUSTOS-E201": CustosError("CUSTOS-E201", "YIELD_DRIFT_EXCEEDED", 403),
    "CUSTOS-E202": CustosError("CUSTOS-E202", "BACKING_RATIO_BELOW_FLOOR", 403),
    "CUSTOS-E203": CustosError("CUSTOS-E203", "TENOR_UNSUPPORTED", 422),
    "CUSTOS-E300": CustosError("CUSTOS-E300", "ORACLE_UNAVAILABLE", 503),
    "CUSTOS-E301": CustosError("CUSTOS-E301", "ORACLE_DATA_STALE", 503),
    "CUSTOS-E400": CustosError("CUSTOS-E400", "DOWNSTREAM_UNREACHABLE", 502),
}
