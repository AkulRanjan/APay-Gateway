from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel


def intent(asset_id: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "envelope_version": "custos/1", "agent_id": "did:web:acme.com:agents:treasury-bot",
        "action": "borrow_against", "asset_id": asset_id, "amount": "50000.00", "currency": "USD",
        "issued_at": now.isoformat(), "expires_at": (now + timedelta(minutes=5)).isoformat(),
    }


def main(base_url: str) -> None:
    console = Console()
    with httpx.Client(base_url=base_url, timeout=10) as client:
        for asset_id in ("TKN-UST-3M-002", "TKN-UST-3M-003", "TKN-UST-3M-001"):
            response = client.post("/v1/intent", json=intent(asset_id))
            payload = response.json()
            console.print(Panel.fit(json.dumps(payload, indent=2), title=f"{asset_id} · HTTP {response.status_code}"))
            if payload.get("verdict") == "ALLOW":
                Path("attestation.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
                console.print("[green]Wrote attestation.json; verify with demo/verify_attestation.py.[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    main(parser.parse_args().base_url)
