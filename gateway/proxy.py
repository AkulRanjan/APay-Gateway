from __future__ import annotations

import base64
import json

import httpx

import config
from models import Attestation, Intent


async def forward(intent: Intent, attestation: Attestation) -> dict:
    """Forward an allowed intent and include its signed proof in a safe HTTP header."""
    assert intent.downstream is not None
    serialized = json.dumps(attestation.model_dump(mode="json"), separators=(",", ":"), ensure_ascii=True)
    headers = {"X-Custos-Attestation": base64.b64encode(serialized.encode("utf-8")).decode("ascii")}
    timeout = httpx.Timeout(config.ORACLE_TIMEOUT_SECONDS, connect=config.ORACLE_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(str(intent.downstream), json=intent.model_dump(mode="json", exclude={"downstream"}), headers=headers)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return {"status_code": response.status_code, "body": body}
    except httpx.HTTPError as exc:
        raise ConnectionError("downstream could not be reached") from exc
