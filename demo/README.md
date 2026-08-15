# Custos demo

Run the complete demonstration from the repository root:

```powershell
python demo/run_local_demo.py
```

It calls the real FastAPI gateway routes in-process and presents four deterministic outcomes:

1. Stale claim → `CUSTOS-E101`
2. Recent but implausible yield → `CUSTOS-E201`
3. Under-backed claim → `CUSTOS-E202`
4. Healthy claim → signed `ALLOW`, independently verified with Ed25519

The runner writes the successful attestation to `demo/attestation.json`. Verify it again in a separate command:

```powershell
python demo/verify_attestation.py demo/attestation.json
```

`run_local_demo.py` substitutes only a fixed 400 bps observation, so the demo is repeatable. The production gateway retains its live Treasury client and fails closed with `CUSTOS-E300` if that source is unreachable.

For the live network version, start the gateway and use the existing HTTP client:

```powershell
python -m uvicorn gateway.server:app
python demo/run_demo.py
```
