from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonicalize(payload: dict[str, Any]) -> bytes:
    """Custos's documented RFC8785-lite canonical form.

    Pydantic has already converted Decimal/datetime values to JSON primitives before
    this function is called. Signature material is deliberately excluded.
    """
    unsigned = {key: value for key, value in payload.items() if key not in {"signature", "public_key"}}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


class AttestationSigner:
    def __init__(self, private_key_path: str | None = None) -> None:
        key_path = private_key_path or os.getenv("CUSTOS_PRIVATE_KEY")
        if key_path:
            pem = Path(key_path).read_bytes()
            loaded = serialization.load_pem_private_key(pem, password=None)
            if not isinstance(loaded, Ed25519PrivateKey):
                raise TypeError("CUSTOS_PRIVATE_KEY must contain an Ed25519 private key")
            self._private_key = loaded
        else:
            self._private_key = Ed25519PrivateKey.generate()

    @property
    def public_key_base64(self) -> str:
        raw = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")

    @property
    def public_key_pem(self) -> str:
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def sign(self, payload: dict[str, Any]) -> str:
        return base64.b64encode(self._private_key.sign(canonicalize(payload))).decode("ascii")
