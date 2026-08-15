"""Standalone verifier: intentionally imports no Custos package modules."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonicalize(payload: dict) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key not in {"signature", "public_key"}}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def verify(payload: dict) -> None:
    signature = base64.b64decode(payload["signature"])
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(payload["public_key"]))
    public_key.verify(signature, canonicalize(payload))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify a Custos ALLOW attestation independently.")
    parser.add_argument("attestation", type=Path)
    args = parser.parse_args()
    verify(json.loads(args.attestation.read_text(encoding="utf-8")))
    print("VALID: Ed25519 signature matches the canonical attestation payload.")
