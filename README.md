<<<<<<< HEAD
# APay-Gateway
=======
# Custos Gateway

Custos prevents an autonomous agent from transacting against a tokenized Treasury claim until the claim is cross-checked against a current U.S. Treasury yield curve observation. It is a plausibility check against market rates, not an audit of a fund's private NAV or holdings.

## Run

```powershell
python -m pip install -r requirements.txt
python -m uvicorn gateway.server:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API. The oracle uses Treasury's official daily XML yield feed, has a 60-second in-process cache, a three-second timeout, and returns `CUSTOS-E300` rather than allowing an unverifiable transaction when the source cannot be reached.

```powershell
python demo/run_demo.py
python demo/verify_attestation.py attestation.json
```

To demonstrate forwarding, start `python -m uvicorn demo.mock_lender:app --port 9000` and add `"downstream": "http://127.0.0.1:9000/loan"` to an intent. Custos forwards only an ALLOW and places a base64-encoded signed attestation in `X-Custos-Attestation`.

## Configuration

`CUSTOS_STALENESS_HOURS`, `CUSTOS_DRIFT_THRESHOLD`, `CUSTOS_BACKING_FLOOR`, `CUSTOS_MAX_OBS_AGE_DAYS`, `CUSTOS_ORACLE_TIMEOUT`, `CUSTOS_CACHE_TTL`, `CUSTOS_ATTESTATION_TTL`, and `CUSTOS_PRIVATE_KEY` are supported. The private-key value is a path to an Ed25519 PEM; without it Custos generates an ephemeral demo key at startup.

The seeds use relative attestation ages, so a healthy claim does not become stale merely because the process has been running. Before a live demo, set the healthy seed's `claimed_yield_bps` to the current 3M observation (and the drifted seed at least 2% away), as claims are intentionally simulated rather than written by the oracle.

## Verify

```powershell
python -m pytest -q
```

The test suite covers all scoring paths, fail-closed behavior, canonical serialization, Ed25519 verification, and Treasury XML normalization.
>>>>>>> 3da9d8f (Project Base)
