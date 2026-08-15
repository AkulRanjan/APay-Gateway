from __future__ import annotations

from datetime import datetime, timezone

import config
from attest.errors import ERRORS
from models import BlockResponse, Claim, Intent, Observation, Scores


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _block(code: str, detail: str, *, asset_id: str | None, scores: Scores | None = None,
           reference: dict | None = None) -> BlockResponse:
    error = ERRORS[code]
    return BlockResponse(
        error=error.code, error_name=error.name, detail=detail, asset_id=asset_id,
        scores=scores, reference=reference, issued_at=utc_now(),
    )


def evaluate(intent: Intent, claim: Claim | None, obs: Observation | None) -> Scores | BlockResponse:
    """Evaluate asset truthfulness; returns scores for ALLOW or a terminal BLOCK.

    Envelope checks are intentionally performed by ``gateway.validation`` first.
    The order below is the public error-precedence contract.
    """
    if claim is None:
        return _block("CUSTOS-E200", "The requested asset is not present in the claim registry.", asset_id=intent.asset_id)
    if obs is None:
        return _block("CUSTOS-E300", "The Treasury oracle could not be reached; Custos fails closed.", asset_id=claim.asset_id)

    age_days = (utc_now().date() - obs.record_date).days
    reference = {
        "source": obs.source, "tenor": obs.tenor,
        "claimed_yield_bps": claim.claimed_yield_bps,
        "observed_yield_bps": obs.observed_yield_bps,
        "record_date": obs.record_date.isoformat(),
    }
    if age_days > config.MAX_OBSERVATION_AGE_DAYS:
        return _block("CUSTOS-E301", f"Treasury observation is {age_days} days old; maximum is {config.MAX_OBSERVATION_AGE_DAYS}.",
                      asset_id=claim.asset_id, reference=reference)

    last_attested = claim.last_attested_at
    if last_attested.tzinfo is None:
        last_attested = last_attested.replace(tzinfo=timezone.utc)
    staleness = max(0.0, (utc_now() - last_attested).total_seconds() / 3600)
    staleness_scores = Scores(staleness_hours=round(staleness, 2), staleness_threshold_hours=config.STALENESS_THRESHOLD_HOURS)
    if staleness > config.STALENESS_THRESHOLD_HOURS:
        return _block("CUSTOS-E101", f"Claim was last attested {staleness:.2f} hours ago; threshold is {config.STALENESS_THRESHOLD_HOURS:.1f} hours.",
                      asset_id=claim.asset_id, scores=staleness_scores, reference=reference)

    if obs.observed_yield_bps <= 0:
        return _block("CUSTOS-E300", "Treasury oracle returned an invalid zero yield; Custos fails closed.", asset_id=claim.asset_id)
    drift = abs(obs.observed_yield_bps - claim.claimed_yield_bps) / obs.observed_yield_bps
    drift_scores = staleness_scores.model_copy(update={
        "yield_drift": round(drift, 6), "yield_drift_threshold": config.DRIFT_THRESHOLD,
    })
    if drift > config.DRIFT_THRESHOLD:
        return _block("CUSTOS-E201", f"Claimed yield {claim.claimed_yield_bps} bps diverges {drift:.2%} from observed {obs.tenor} yield of {obs.observed_yield_bps} bps; threshold is {config.DRIFT_THRESHOLD:.1%}.",
                      asset_id=claim.asset_id, scores=drift_scores, reference=reference)

    implied_liability = claim.tokens_outstanding * claim.claimed_nav_per_token
    ratio = float(claim.claimed_backing_usd / implied_liability)
    scores = drift_scores.model_copy(update={
        "backing_ratio": round(ratio, 6), "backing_ratio_floor": config.BACKING_FLOOR,
    })
    if ratio < config.BACKING_FLOOR:
        return _block("CUSTOS-E202", f"Backing ratio is {ratio:.4f}; floor is {config.BACKING_FLOOR:.4f}.",
                      asset_id=claim.asset_id, scores=scores, reference=reference)
    return scores
