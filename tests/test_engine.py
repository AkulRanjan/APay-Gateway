from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from attest.engine import evaluate
from attest.signing import AttestationSigner, canonicalize
from models import Claim, Intent, Observation


def now() -> datetime:
    return datetime.now(timezone.utc)


def intent(asset_id: str = "asset") -> Intent:
    return Intent(envelope_version="custos/1", agent_id="did:test:agent", action="trade", asset_id=asset_id,
                  amount=Decimal("1"), currency="USD", issued_at=now(), expires_at=now() + timedelta(minutes=1))


def claim(**overrides) -> Claim:
    values = {
        "asset_id": "asset", "issuer": "Issuer", "underlying_tenor": "3M",
        "claimed_nav_per_token": Decimal("1"), "claimed_backing_usd": Decimal("100"),
        "tokens_outstanding": Decimal("100"), "claimed_yield_bps": 400,
        "last_attested_at": now() - timedelta(hours=1), "chain": "ethereum", "contract_address": "0x1",
    }
    values.update(overrides)
    return Claim(**values)


def observation(**overrides) -> Observation:
    values = {"source": "test", "tenor": "3M", "observed_yield_bps": 400,
              "record_date": now().date(), "fetched_at": now()}
    values.update(overrides)
    return Observation(**values)


def test_healthy_claim_allows():
    result = evaluate(intent(), claim(), observation())
    assert result.yield_drift == 0
    assert result.backing_ratio == 1


def test_stale_claim_short_circuits_first():
    result = evaluate(intent(), claim(last_attested_at=now() - timedelta(hours=25), claimed_yield_bps=1), observation())
    assert result.error == "CUSTOS-E101"


def test_yield_drift_blocks_recent_claim():
    result = evaluate(intent(), claim(claimed_yield_bps=350), observation())
    assert result.error == "CUSTOS-E201"


def test_oracle_failure_fails_closed():
    result = evaluate(intent(), claim(), None)
    assert result.error == "CUSTOS-E300"


def test_backing_floor_blocks_after_valid_market_checks():
    result = evaluate(intent(), claim(claimed_backing_usd=Decimal("94")), observation())
    assert result.error == "CUSTOS-E202"


def test_ed25519_signature_round_trip():
    signer = AttestationSigner()
    payload = {"verdict": "ALLOW", "amount": "1.00", "signature": None, "public_key": signer.public_key_base64}
    signature = signer.sign(payload)
    from base64 import b64decode
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    Ed25519PublicKey.from_public_bytes(b64decode(signer.public_key_base64)).verify(b64decode(signature), canonicalize(payload))


def test_canonical_form_is_stable():
    first = canonicalize({"b": 2, "a": 1, "signature": "ignored"})
    second = canonicalize({"a": 1, "b": 2, "public_key": "ignored"})
    assert first == second == b'{"a":1,"b":2}'
