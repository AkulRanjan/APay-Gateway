"""Run a complete, reproducible Custos demo without starting external services.

This invokes the actual FastAPI gateway through its ASGI HTTP interface. Only the
Treasury observation is fixed so every presentation has the intended outcomes.
Production continues to use ``oracle.treasury.TreasuryOracle`` and its live feed.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from rich.console import Console
from rich.table import Table

# Support the documented ``python demo/run_local_demo.py`` invocation.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo.verify_attestation import verify
from gateway import server
from models import Observation


class DemoOracle:
    """A known-good 4.00% Treasury observation for deterministic demo outcomes."""

    async def get_observation(self, tenor: str) -> Observation:
        return Observation(
            source="demo.fixed-observation",
            tenor=tenor,
            observed_yield_bps=400,
            record_date=datetime.now(timezone.utc).date(),
            fetched_at=datetime.now(timezone.utc),
        )


def make_intent(asset_id: str) -> dict:
    issued_at = datetime.now(timezone.utc)
    return {
        "envelope_version": "custos/1",
        "agent_id": "did:web:acme.com:agents:treasury-bot",
        "action": "borrow_against",
        "asset_id": asset_id,
        "amount": "50000.00",
        "currency": "USD",
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=5)).isoformat(),
    }


async def run() -> None:
    console = Console()
    original_oracle = server.oracle
    server.oracle = DemoOracle()
    scenarios = [
        ("TKN-UST-3M-002", "Stale claim", "CUSTOS-E101"),
        ("TKN-UST-3M-003", "Recent but drifted claim", "CUSTOS-E201"),
        ("TKN-UST-6M-004", "Under-backed claim", "CUSTOS-E202"),
        ("TKN-UST-3M-001", "Healthy claim", "ALLOW"),
    ]
    table = Table(title="Custos Gateway — deterministic local demo")
    table.add_column("Scenario")
    table.add_column("Asset")
    table.add_column("HTTP")
    table.add_column("Result")
    table.add_column("Expected")

    try:
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://custos.demo") as client:
            for asset_id, name, expected in scenarios:
                response = await client.post("/v1/intent", json=make_intent(asset_id))
                payload = response.json()
                result = payload.get("error", payload.get("verdict", "UNKNOWN"))
                style = "green" if result == expected else "red"
                table.add_row(name, asset_id, str(response.status_code), f"[{style}]{result}[/{style}]", expected)

                if payload.get("verdict") == "ALLOW":
                    output = Path(__file__).with_name("attestation.json")
                    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    verify(payload)
                    console.print(f"[green]Signature verified independently. Attestation written to {output}[/green]")
    finally:
        server.oracle = original_oracle

    console.print(table)
    console.print("[dim]Demo mode uses a fixed 400 bps Treasury observation; normal gateway mode remains live and fail-closed.[/dim]")


if __name__ == "__main__":
    asyncio.run(run())
