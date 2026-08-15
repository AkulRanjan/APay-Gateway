from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import config
from attest import AttestationSigner, evaluate
from attest.errors import ERRORS
from claims import ClaimRegistry
from gateway.proxy import forward
from gateway.validation import validate_temporal_envelope
from models import Attestation, BlockResponse, Intent
from oracle.treasury import TreasuryOracle, UnsupportedTenor

app = FastAPI(title="Custos Gateway", version="0.1.0", description="Real-time tokenized Treasury claim attestation gateway.")
registry = ClaimRegistry()
oracle = TreasuryOracle()
signer = AttestationSigner()


def now() -> datetime:
    return datetime.now(timezone.utc)


def json_response(model: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=jsonable_encoder(model))


def block(code: str, detail: str, *, asset_id: str | None = None) -> BlockResponse:
    error = ERRORS[code]
    return BlockResponse(error=error.code, error_name=error.name, detail=detail, asset_id=asset_id, issued_at=now())


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    error = ERRORS["CUSTOS-E100"]
    response = BlockResponse(error=error.code, error_name=error.name,
                             detail="Envelope schema validation failed.", issued_at=now())
    return json_response(response, error.status_code)


def make_attestation(intent: Intent, scores, claim, observation) -> Attestation:
    issued_at = now()
    reference = {
        "source": observation.source,
        "tenor": observation.tenor,
        "claimed_yield_bps": claim.claimed_yield_bps,
        "observed_yield_bps": observation.observed_yield_bps,
        "record_date": observation.record_date.isoformat(),
    }
    attestation = Attestation(
        attestation_id=f"att_{uuid.uuid4().hex}", asset_id=intent.asset_id,
        agent_id=intent.agent_id, action=intent.action.value, amount=intent.amount,
        scores=scores, reference=reference, issued_at=issued_at,
        expires_at=issued_at + timedelta(seconds=config.ATTESTATION_TTL_SECONDS),
        public_key=signer.public_key_base64,
    )
    payload = attestation.model_dump(mode="json")
    attestation.signature = signer.sign(payload)
    return attestation


async def assess(intent: Intent):
    claim = registry.get_claim(intent.asset_id)
    if claim is None:
        result = evaluate(intent, None, None)
        return result, None, None
    try:
        observation = await oracle.get_observation(claim.underlying_tenor)
    except UnsupportedTenor:
        return block("CUSTOS-E203", f"Underlying tenor {claim.underlying_tenor} has no Treasury yield mapping.", asset_id=claim.asset_id), claim, None
    return evaluate(intent, claim, observation), claim, observation


@app.post("/v1/intent", response_model=None)
async def post_intent(intent: Intent):
    temporal_error = validate_temporal_envelope(intent)
    if temporal_error:
        return json_response(temporal_error, ERRORS[temporal_error.error].status_code)
    result, claim, observation = await assess(intent)
    if isinstance(result, BlockResponse):
        return json_response(result, ERRORS[result.error].status_code)
    attestation = make_attestation(intent, result, claim, observation)
    if intent.downstream is None:
        return json_response(attestation)
    try:
        downstream = await forward(intent, attestation)
    except ConnectionError:
        failure = block("CUSTOS-E400", "Attestation was allowed, but the downstream service could not be reached.", asset_id=intent.asset_id)
        return json_response(failure, ERRORS[failure.error].status_code)
    return json_response({"attestation": attestation, "downstream": downstream})


@app.get("/v1/assets")
async def list_assets():
    return json_response({"assets": registry.list_claims()})


@app.get("/v1/assets/{asset_id}", response_model=None)
async def get_asset(asset_id: str):
    claim = registry.get_claim(asset_id)
    if claim is None:
        failure = block("CUSTOS-E200", "The requested asset is not present in the claim registry.", asset_id=asset_id)
        return json_response(failure, ERRORS[failure.error].status_code)
    diagnostic_intent = Intent(envelope_version="custos/1", agent_id="diagnostic", action="trade", asset_id=asset_id,
                               amount="0.01", currency="USD", issued_at=now(), expires_at=now() + timedelta(minutes=1))
    result, _, observation = await assess(diagnostic_intent)
    return json_response({"claim": claim, "observation": observation, "evaluation": result})


@app.get("/v1/pubkey")
async def get_public_key():
    return {"algorithm": "Ed25519", "public_key": signer.public_key_base64, "public_key_pem": signer.public_key_pem}


@app.get("/v1/health", response_model=None)
async def health():
    try:
        observation = await oracle.get_observation("3M")
    except UnsupportedTenor:  # impossible unless code is modified
        observation = None
    status = "ok" if observation else "degraded"
    return json_response({"status": status, "oracle_reachable": observation is not None, "observation": observation}, 200 if observation else 503)
