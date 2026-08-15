from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from demo.verify_attestation import verify
from gateway import server
from models import Observation


class FixedOracle:
    async def get_observation(self, tenor: str):
        return Observation(source="test-oracle", tenor=tenor, observed_yield_bps=400,
                           record_date=datetime.now(timezone.utc).date(), fetched_at=datetime.now(timezone.utc))


def payload(asset_id: str = "TKN-UST-3M-001") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "envelope_version": "custos/1", "agent_id": "did:test:agent", "action": "trade",
        "asset_id": asset_id, "amount": "1.00", "currency": "USD",
        "issued_at": now.isoformat(), "expires_at": (now + timedelta(minutes=1)).isoformat(),
    }


def test_malformed_envelope_is_structured_400():
    response = TestClient(server.app).post("/v1/intent", json={})
    assert response.status_code == 400
    assert response.json()["error"] == "CUSTOS-E100"


def test_allow_is_signed_and_independently_verifiable(monkeypatch):
    monkeypatch.setattr(server, "oracle", FixedOracle())
    response = TestClient(server.app).post("/v1/intent", json=payload())
    assert response.status_code == 200
    attestation = response.json()
    assert attestation["verdict"] == "ALLOW"
    verify(attestation)


def test_unknown_asset_precedes_oracle_fetch(monkeypatch):
    monkeypatch.setattr(server, "oracle", FixedOracle())
    response = TestClient(server.app).post("/v1/intent", json=payload("does-not-exist"))
    assert response.status_code == 404
    assert response.json()["error"] == "CUSTOS-E200"
