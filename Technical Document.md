# Custos Gateway — Technical Specification

**Real-time asset attestation gateway for agent-driven transactions on tokenized Treasuries**

Version 0.1 · Codex Community Build Hackathon, Bangalore · 15 August 2026

---

## 1. Problem Statement

Tokenized real-world assets have crossed roughly $31–33 billion in on-chain value, and tokenized US Treasuries are the single largest category at roughly $13–16 billion. As of early 2026, regulated tokenized Treasury funds began entering DeFi rails and can now serve as collateral in decentralized lending.

In parallel, autonomous agents are becoming economic actors. They hold wallets, negotiate, and execute transactions without a human in the loop. Two trust layers already exist for them:

- **Identity and intent layers** verify *whether an agent is allowed to act* (cryptographic passports, boundary enforcement, kill switches).
- **Credit layers** verify *whether an agent should receive liquidity* (risk-scored lending against programmable guardrails).

Neither layer verifies **whether the asset the agent is transacting against is still telling the truth**.

A tokenized asset carries a claim: "this token represents $X of short-duration Treasury exposure, NAV as of date D." The blockchain has no independent way to confirm that claim is current. Updating it requires someone to push new data. There is lag, there are incentives to delay, and there is frequently no verification step at all between reality and the on-chain claim.

**Custos closes that gap.** It is a gateway that sits between an agent and any transaction against a tokenized asset. It cross-checks the on-chain claim against live off-chain market data, computes drift and staleness scores, and returns either a cryptographically signed attestation (allow) or a structured machine-readable error (block) before any capital moves.

---

## 2. Design Principles

| Principle | Consequence |
|---|---|
| **Gateway, not library** | Custos is a network hop with a real request/response boundary. Integration is a config change, not a code rewrite. |
| **Fail closed** | If the off-chain oracle is unreachable, block. A security component that fails open is not a security component. |
| **Deterministic verdicts** | No LLM in the decision path. Scoring is arithmetic against thresholds, fully explainable and reproducible. |
| **Signed, verifiable output** | Every allow carries an Ed25519 signature that any third party can verify independently, offline. |
| **Structured errors** | Every block returns a machine-readable code, not a generic 403. Agents can branch on the reason. |
| **Real data, not mocks, on the truth side** | The off-chain source is a live public government API. Only the on-chain claim is simulated. |

---

## 3. System Architecture

### 3.1 Request flow

```
                        ┌──────────────┐
                        │    AGENT     │
                        │  (borrower)  │
                        └──────┬───────┘
                               │ POST /v1/intent
                               │ { agent_id, action, asset_id, amount }
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │                    CUSTOS GATEWAY                        │
    │                                                          │
    │   ┌────────────────────────────────────────────────┐    │
    │   │  S1  Envelope validation (schema, expiry)      │    │
    │   └───────────────────┬────────────────────────────┘    │
    │                       ▼                                  │
    │   ┌────────────────────────────────────────────────┐    │
    │   │  S2  Claim resolution                          │    │
    │   │      asset_id → on-chain claim record          │    │
    │   └───────────────────┬────────────────────────────┘    │
    │                       ▼                                  │
    │   ┌────────────────────────────────────────────────┐    │
    │   │  S3  Oracle fetch          ──────────────────► │────┼──► api.fiscaldata
    │   │      live Treasury yield for matching tenor    │    │    .treasury.gov
    │   │      (60s cache, 3s timeout, fail closed)      │ ◄──┼───
    │   └───────────────────┬────────────────────────────┘    │
    │                       ▼                                  │
    │   ┌────────────────────────────────────────────────┐    │
    │   │  S4  Scoring engine                            │    │
    │   │      staleness · yield drift · backing ratio   │    │
    │   └───────────────────┬────────────────────────────┘    │
    │                       ▼                                  │
    │   ┌────────────────────────────────────────────────┐    │
    │   │  S5  Verdict + Ed25519 signing                 │    │
    │   └───────┬────────────────────────┬───────────────┘    │
    │           │ ALLOW                  │ BLOCK               │
    └───────────┼────────────────────────┼─────────────────────┘
                ▼                        ▼
    ┌───────────────────────┐   ┌──────────────────────┐
    │  Proxy to downstream  │   │  HTTP 403            │
    │  + X-Custos-          │   │  { error: "CUSTOS-   │
    │    Attestation header │   │    E201", detail:…}  │
    └───────────────────────┘   └──────────────────────┘
              │
              ▼
    ┌───────────────────────┐
    │  Lending protocol /   │
    │  DEX / chain          │
    └───────────────────────┘
```

### 3.2 Module map

| Module | Package path | Responsibility | Depends on |
|---|---|---|---|
| **Gateway** | `gateway/` | HTTP server, routing, envelope validation, downstream proxy | Attest, Claims |
| **Claims** | `claims/` | On-chain claim registry (seeded), asset lookup | — |
| **Oracle** | `oracle/` | Treasury API client, response normalization, cache, timeout | — |
| **Attest** | `attest/` | Scoring engine, verdict logic, Ed25519 signing, error taxonomy | Oracle |
| **Demo** | `demo/` | Scripted demo runner, independent signature verifier | — (HTTP only) |

Dependency direction is strictly one-way. `Oracle` and `Claims` have no internal dependencies, which is what makes the parallel build viable.

---

## 4. Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Fastest path to a signed HTTP service; strong crypto and async HTTP libraries |
| Web framework | FastAPI | Automatic request validation from type hints, built-in OpenAPI docs (useful in demo), async native |
| ASGI server | uvicorn | Standard FastAPI pairing |
| Data validation | Pydantic v2 | Envelope and attestation schemas as declarative models; validation errors map cleanly to `CUSTOS-E100` |
| HTTP client | httpx | Async, timeout control, connection pooling for the oracle |
| Cryptography | `cryptography` (Ed25519) | Same primitive AIP uses; small keys, fast signing, easy independent verification |
| Cache | In-process dict with TTL | 2-hour build. Redis is unjustified complexity for a single-process demo |
| Demo output | rich | Readable terminal output during a live demo beats raw JSON |
| Config | Environment variables + `config.py` defaults | Thresholds must be tunable live without a code edit |

**Deliberately excluded:** database (seed data is a JSON file), Redis, Docker, message queue, frontend framework. Every one of these is a plausible v2 addition and a guaranteed v1 time sink.

---

## 5. Data Contracts

### 5.1 Intent envelope (agent → gateway)

```json
{
  "envelope_version": "custos/1",
  "agent_id": "did:web:acme.com:agents:treasury-bot",
  "action": "borrow_against",
  "asset_id": "TKN-UST-3M-001",
  "amount": 50000.00,
  "currency": "USD",
  "issued_at": "2026-08-15T11:30:00Z",
  "expires_at": "2026-08-15T11:35:00Z",
  "downstream": "http://localhost:9000/loan"
}
```

**Field rules:**

| Field | Type | Required | Validation |
|---|---|---|---|
| `envelope_version` | string | yes | must equal `custos/1` |
| `agent_id` | string | yes | non-empty; DID format not enforced in v1 |
| `action` | enum | yes | one of `borrow_against`, `trade`, `redeem` |
| `asset_id` | string | yes | must resolve in claim registry, else `CUSTOS-E200` |
| `amount` | decimal | yes | > 0 |
| `currency` | string | yes | ISO-4217; v1 accepts `USD` only |
| `issued_at` | ISO-8601 UTC | yes | not more than 5 min in the future (clock skew guard) |
| `expires_at` | ISO-8601 UTC | yes | must be > now, else `CUSTOS-E102` |
| `downstream` | URL | no | if absent, gateway returns verdict without proxying |

### 5.2 On-chain claim record (seeded, simulates chain state)

```json
{
  "asset_id": "TKN-UST-3M-001",
  "issuer": "Meridian Short Duration Treasury Fund",
  "underlying_tenor": "3M",
  "claimed_nav_per_token": 1.0000,
  "claimed_backing_usd": 10000000.00,
  "tokens_outstanding": 10000000,
  "claimed_yield_bps": 432,
  "last_attested_at": "2026-08-15T09:00:00Z",
  "chain": "ethereum",
  "contract_address": "0x0000000000000000000000000000000000000001"
}
```

`underlying_tenor` is the join key to the Treasury yield curve. Supported values map to CMT tenors: `1M`, `1.5M`, `2M`, `3M`, `4M`, `6M`, `1Y`, `2Y`.

### 5.3 Observation (oracle → scoring engine)

```json
{
  "source": "api.fiscaldata.treasury.gov",
  "dataset": "daily_treasury_yield_curve",
  "tenor": "3M",
  "observed_yield_bps": 434,
  "record_date": "2026-08-14",
  "fetched_at": "2026-08-15T11:29:58Z",
  "cache_hit": false
}
```

### 5.4 Attestation (gateway → agent, ALLOW path)

```json
{
  "attestation_id": "att_01J9F7K3M2X8Q4",
  "verdict": "ALLOW",
  "asset_id": "TKN-UST-3M-001",
  "agent_id": "did:web:acme.com:agents:treasury-bot",
  "action": "borrow_against",
  "amount": 50000.00,
  "scores": {
    "staleness_hours": 2.50,
    "staleness_threshold_hours": 24.0,
    "yield_drift": 0.0046,
    "yield_drift_threshold": 0.02,
    "backing_ratio": 1.0000,
    "backing_ratio_floor": 1.0
  },
  "reference": {
    "source": "api.fiscaldata.treasury.gov",
    "tenor": "3M",
    "claimed_yield_bps": 432,
    "observed_yield_bps": 434,
    "record_date": "2026-08-14"
  },
  "issued_at": "2026-08-15T11:30:00Z",
  "expires_at": "2026-08-15T11:35:00Z",
  "signature": "<base64 Ed25519 signature over canonical payload>",
  "public_key": "<base64 Ed25519 public key>",
  "signature_alg": "Ed25519",
  "canonicalization": "JCS/RFC8785-lite"
}
```

### 5.5 Block response (BLOCK path, HTTP 403)

```json
{
  "verdict": "BLOCK",
  "error": "CUSTOS-E201",
  "error_name": "YIELD_DRIFT_EXCEEDED",
  "detail": "Claimed yield 432 bps diverges 8.6% from observed 3M yield of 396 bps; threshold is 2.0%.",
  "asset_id": "TKN-UST-3M-001",
  "scores": {
    "yield_drift": 0.0857,
    "yield_drift_threshold": 0.02
  },
  "reference": {
    "source": "api.fiscaldata.treasury.gov",
    "tenor": "3M",
    "observed_yield_bps": 396,
    "record_date": "2026-08-14"
  },
  "issued_at": "2026-08-15T11:31:00Z"
}
```

Block responses are also signed in the full design (a signed denial is auditable evidence). If time is short, signing the ALLOW path only is an acceptable v1 cut; state it explicitly rather than leaving it ambiguous.

---

## 6. Scoring Engine

Three independent signals. Evaluation short-circuits on first failure, in the order below, so the returned error code is the most fundamental problem rather than an arbitrary one.

### 6.1 Signal 1 — Staleness

Measures how long since the on-chain claim was last refreshed. This catches an asset whose backing data has simply gone unmaintained.

```
staleness_hours = (now_utc − claim.last_attested_at) / 3600

if staleness_hours > STALENESS_THRESHOLD_HOURS:
    → BLOCK, CUSTOS-E101
```

Default `STALENESS_THRESHOLD_HOURS = 24`. Justification: tokenized Treasury funds publish NAV daily. A claim older than one business day is by definition unverified against a published value.

### 6.2 Signal 2 — Yield drift

Measures whether the claimed yield is still plausible against the live market for the same tenor. This catches an asset whose claim is *recent* but *wrong* — the more dangerous case, because staleness checks alone would pass it.

```
observed = oracle.yield_bps(claim.underlying_tenor)
claimed  = claim.claimed_yield_bps

yield_drift = |observed − claimed| / observed

if yield_drift > DRIFT_THRESHOLD:
    → BLOCK, CUSTOS-E201
```

Default `DRIFT_THRESHOLD = 0.02` (2% relative). At a 4.3% yield this is roughly 9 bps of tolerance, which absorbs normal intraday movement and rounding while catching a genuinely mispriced claim.

**Why relative rather than absolute:** a 10 bps gap is noise at a 4.3% yield and material at a 0.5% yield. Relative drift stays meaningful across rate regimes.

### 6.3 Signal 3 — Backing ratio

Measures crude over- or under-collateralization: does the claimed dollar backing actually cover the tokens issued at the claimed NAV?

```
implied_liability = claim.tokens_outstanding × claim.claimed_nav_per_token
backing_ratio     = claim.claimed_backing_usd / implied_liability

if backing_ratio < BACKING_FLOOR:
    → BLOCK, CUSTOS-E202
```

Default `BACKING_FLOOR = 1.0`. This is an internal-consistency check on the claim itself and needs no oracle call, so it is cheap and always runs.

### 6.4 Verdict resolution

```python
def evaluate(intent: Intent, claim: Claim, obs: Observation | None) -> Verdict:
    # Envelope-level checks happen upstream in the gateway (E100, E102).

    if claim is None:
        return Block("CUSTOS-E200", "UNKNOWN_ASSET")

    if obs is None:                      # oracle unreachable → fail closed
        return Block("CUSTOS-E300", "ORACLE_UNAVAILABLE")

    if obs.age_days > MAX_OBSERVATION_AGE_DAYS:
        return Block("CUSTOS-E301", "ORACLE_DATA_STALE")

    staleness = hours_since(claim.last_attested_at)
    if staleness > STALENESS_THRESHOLD_HOURS:
        return Block("CUSTOS-E101", "CLAIM_STALE", scores={...})

    drift = abs(obs.yield_bps - claim.claimed_yield_bps) / obs.yield_bps
    if drift > DRIFT_THRESHOLD:
        return Block("CUSTOS-E201", "YIELD_DRIFT_EXCEEDED", scores={...})

    ratio = claim.claimed_backing_usd / (claim.tokens_outstanding
                                          * claim.claimed_nav_per_token)
    if ratio < BACKING_FLOOR:
        return Block("CUSTOS-E202", "BACKING_RATIO_BELOW_FLOOR", scores={...})

    return Allow(scores={...}, reference={...})
```

**This function is the single interface contract between worktrees.** Freeze its signature before splitting work.

---

## 7. Error Taxonomy

Mirrors the `AIP-Exxx` convention so Custos reads as a peer component in the agent-trust stack rather than a standalone tool.

| Code | Name | Category | HTTP | Meaning |
|---|---|---|---|---|
| `CUSTOS-E100` | `MALFORMED_ENVELOPE` | Envelope | 400 | Schema validation failed |
| `CUSTOS-E101` | `CLAIM_STALE` | Envelope | 403 | On-chain claim not refreshed within threshold |
| `CUSTOS-E102` | `INTENT_EXPIRED` | Envelope | 400 | `expires_at` is in the past |
| `CUSTOS-E103` | `CLOCK_SKEW` | Envelope | 400 | `issued_at` implausibly far in the future |
| `CUSTOS-E200` | `UNKNOWN_ASSET` | Asset state | 404 | `asset_id` not in claim registry |
| `CUSTOS-E201` | `YIELD_DRIFT_EXCEEDED` | Asset state | 403 | Claimed yield diverges from live market beyond threshold |
| `CUSTOS-E202` | `BACKING_RATIO_BELOW_FLOOR` | Asset state | 403 | Claimed backing does not cover implied liability |
| `CUSTOS-E203` | `TENOR_UNSUPPORTED` | Asset state | 422 | Claim references a tenor with no yield curve mapping |
| `CUSTOS-E300` | `ORACLE_UNAVAILABLE` | Oracle | 503 | Off-chain source unreachable; fail closed |
| `CUSTOS-E301` | `ORACLE_DATA_STALE` | Oracle | 503 | Off-chain data itself older than tolerance |
| `CUSTOS-E400` | `DOWNSTREAM_UNREACHABLE` | Proxy | 502 | Verdict was ALLOW but downstream call failed |

---

## 8. Oracle Layer

### 8.1 Source

**US Treasury Fiscal Data API** — `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/`

Properties that make it the right choice:

- Open access with no account, registration, or API token required
- RESTful, GET-only, JSON by default (also supports CSV and XML via `format=`)
- Supports field selection (`fields=`), filtering (`filter=` with `lt`, `lte`, `gt`, `gte`, `eq`, `in`), sorting (`sort=`, prefix `-` for descending), and pagination (`page[size]=`, `page[number]=`)
- Returns a `meta` object with `count`, `dataTypes`, `dataFormats`, and `total-count`
- Data is explicitly offered free and without restriction for commercial or non-commercial use

**Pre-build verification required.** The Fiscal Data platform exposes 164 endpoints across its datasets. Confirm the exact endpoint path for daily par yield curve rates with a live `curl` before building against it. Fallback source if the endpoint path proves awkward: `home.treasury.gov` publishes the same daily par yield curve as an XML feed and a downloadable CSV. Wire the client behind an interface so either source can back it.

**Important framing note:** this API supplies *Treasury market rates*, not the internal NAV of any specific tokenized fund. Issuer NAV feeds are not publicly available. Custos therefore checks whether a claimed yield is **plausible against the live market for its tenor**, not against a fund's private books. State this precisely in the demo — it is both the honest claim and the defensible one.

### 8.2 Client behaviour

| Concern | Implementation |
|---|---|
| Timeout | 3s connect, 3s read. Exceeded → return `None` → `CUSTOS-E300` |
| Cache | In-process dict keyed by tenor, 60s TTL. Prevents hammering the API across demo runs |
| Retry | One retry on connection error, no retry on 4xx |
| Normalization | Percent → basis points (`4.32%` → `432 bps`), stored as int |
| Freshness | Yield curve publishes on business days. `MAX_OBSERVATION_AGE_DAYS = 4` tolerates a long weekend |
| Fail mode | Closed. No observation means no attestation |

### 8.3 Tenor mapping

| Claim `underlying_tenor` | CMT series |
|---|---|
| `1M` | 1 Mo |
| `1.5M` | 1.5 Mo |
| `2M` | 2 Mo |
| `3M` | 3 Mo |
| `4M` | 4 Mo |
| `6M` | 6 Mo |
| `1Y` | 1 Year |
| `2Y` | 2 Year |

Unmapped tenor → `CUSTOS-E203`.

---

## 9. Cryptographic Design

### 9.1 Primitive

**Ed25519**, via the `cryptography` package. Chosen to match the primitive used by AIP, keeping Custos attestations verifiable by the same tooling an agent already runs for intent envelopes.

### 9.2 Key management

- Keypair generated at gateway startup if `CUSTOS_PRIVATE_KEY` is unset, otherwise loaded from PEM at that path
- Public key exposed at `GET /v1/pubkey` in base64 and PEM
- Private key never leaves the process and is never logged

For v1 this is an ephemeral per-run key, which is correct for a demo. Production would use a persistent key with a published DID document.

### 9.3 Canonical signing payload

Signature covers a deterministic serialization of the attestation *excluding* the `signature` and `public_key` fields:

```
canonical = json.dumps(
    {k: v for k, v in attestation.items()
     if k not in ("signature", "public_key")},
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True,
)
signature = ed25519_private_key.sign(canonical.encode("utf-8"))
```

Sorted keys and tight separators give byte-stable output across runs and languages. Document this exactly, because an independent verifier must reproduce it byte-for-byte.

### 9.4 Independent verification

`demo/verify_attestation.py` is a standalone script that imports nothing from the gateway. It takes an attestation JSON file, reconstructs the canonical payload, and verifies the signature against the embedded public key.

**This script is not optional.** It is the artifact that converts "cryptographically signed" from a marketing phrase into a demonstrated property. Running it live, in a separate terminal, against a file the gateway just produced, is the strongest 15 seconds of the demo.

---

## 10. API Surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/intent` | Primary gateway endpoint. Evaluate and allow/block |
| `GET` | `/v1/assets` | List seeded assets and their current claim state |
| `GET` | `/v1/assets/{asset_id}` | Single claim record plus live observation and computed scores, without executing anything |
| `GET` | `/v1/pubkey` | Gateway public key for attestation verification |
| `GET` | `/v1/health` | Liveness plus oracle reachability |
| `GET` | `/docs` | FastAPI auto-generated OpenAPI UI |

`GET /v1/assets/{asset_id}` is worth building early: it is a read-only diagnostic that lets you confirm scoring works before the full request path exists, and it is useful during the demo to show *why* an asset is about to be blocked.

---

## 11. Seed Data Design

Three assets, each engineered to exercise exactly one failure path. Yields should be set relative to the actual live 3M rate on the day (approximately 4.3%) so the numbers read as plausible.

| Asset ID | Scenario | `last_attested_at` | `claimed_yield_bps` | Expected verdict |
|---|---|---|---|---|
| `TKN-UST-3M-001` | Healthy | now − 2h | live ± 2 bps | `ALLOW` |
| `TKN-UST-3M-002` | Stale claim | now − 72h | live ± 2 bps | `BLOCK` `CUSTOS-E101` |
| `TKN-UST-3M-003` | Drifted claim | now − 1h | live − 40 bps | `BLOCK` `CUSTOS-E201` |

Asset 003 is the important one: **recent but wrong**. It demonstrates that a naive staleness check would have passed it, which is the argument for why drift scoring exists.

Optional fourth asset for the backing-ratio path:

| `TKN-UST-6M-004` | Under-backed | now − 1h | live ± 2 bps, backing 0.94× | `BLOCK` `CUSTOS-E202` |

Seed `last_attested_at` values as **relative offsets computed at load time**, not hardcoded timestamps. A hardcoded timestamp silently becomes "stale" as the day progresses and will break the healthy-asset demo path at the worst possible moment.

---

## 12. Parallel Build Plan (Codex Worktrees)

### 12.1 Pre-split requirement

Write `AGENTS.md` at repo root containing sections 3, 5, 6, and 7 of this document before launching any worktree. Codex needs the data contracts and the `evaluate()` signature as context; without it each worktree invents its own schema and the merge fails.

### 12.2 Worktree A — Gateway and schemas

**Owns:** `gateway/`, `models/`

- FastAPI application, all routes in section 10
- Pydantic models for `Intent`, `Claim`, `Observation`, `Attestation`, `BlockResponse`
- Envelope validation producing `CUSTOS-E100`, `E102`, `E103`
- Downstream proxy on ALLOW, attaching `X-Custos-Attestation` header
- Imports `attest.evaluate` — stub it locally until Worktree B merges

**Done when:** `POST /v1/intent` returns a hardcoded ALLOW for any well-formed envelope and correct error codes for malformed ones.

### 12.3 Worktree B — Oracle and attestation engine

**Owns:** `oracle/`, `attest/`

- Treasury API client per section 8, with cache, timeout, normalization, tenor mapping
- Scoring engine per section 6
- Ed25519 keypair, canonical serialization, signing per section 9
- Error taxonomy module per section 7

**Done when:** a local script calls `evaluate()` with a fabricated claim and gets correct verdicts against **live** Treasury data.

**This is the critical path.** If it is not done, nothing else matters. Start it first and give it the most attention.

### 12.4 Worktree C — Seed data and demo harness

**Owns:** `claims/`, `demo/`

- `claims/seed.json` plus loader that computes relative timestamps at load
- `claims/registry.py` exposing `get_claim(asset_id) -> Claim | None`
- `demo/run_demo.py`: fires the three (or four) scenarios in sequence, prints verdicts with `rich`
- `demo/verify_attestation.py`: standalone signature verifier per section 9.4

**Done when:** the demo script runs against a stubbed gateway and prints readable output.

### 12.5 Merge sequence

```
B → A       (attest.evaluate replaces the stub)
C → A       (registry replaces hardcoded lookup)
integration test → freeze
```

B before C. If B slips, C can still be demoed against stub verdicts; if A slips, nothing is demoable.

---

## 13. Configuration

All thresholds environment-overridable so they can be tuned live if a demo asset behaves unexpectedly.

```python
# config.py
STALENESS_THRESHOLD_HOURS   = float(env("CUSTOS_STALENESS_HOURS", 24.0))
DRIFT_THRESHOLD             = float(env("CUSTOS_DRIFT_THRESHOLD", 0.02))
BACKING_FLOOR               = float(env("CUSTOS_BACKING_FLOOR", 1.0))
MAX_OBSERVATION_AGE_DAYS    = int(env("CUSTOS_MAX_OBS_AGE_DAYS", 4))
ORACLE_TIMEOUT_SECONDS      = float(env("CUSTOS_ORACLE_TIMEOUT", 3.0))
ORACLE_CACHE_TTL_SECONDS    = int(env("CUSTOS_CACHE_TTL", 60))
ATTESTATION_TTL_SECONDS     = int(env("CUSTOS_ATTESTATION_TTL", 300))
FAIL_MODE                   = env("CUSTOS_FAIL_MODE", "closed")   # closed | open
```

`FAIL_MODE` defaults to `closed` and should stay there. Its presence as a config key is itself a talking point: the choice is deliberate and documented, not accidental.

---

## 14. Testing Strategy

Given the time budget, test only what protects the demo.

| Test | Why it matters |
|---|---|
| `evaluate()` returns ALLOW for healthy fixture | Core happy path |
| `evaluate()` returns `E101` for stale fixture | Demo beat 1 |
| `evaluate()` returns `E201` for drifted fixture | Demo beat 2 |
| `evaluate()` returns `E300` when oracle returns `None` | Fail-closed guarantee |
| Signature round-trip: sign then verify | Cryptographic claim holds |
| Canonical form is byte-stable across two runs | Independent verifier will actually work |
| Live oracle fetch returns a plausible bps value (300–600) | Catches API shape changes |

Skip: load testing, proxy failure modes, concurrency, full envelope fuzzing.

---

## 15. Repository Structure

```
custos/
├── AGENTS.md                    # Context for Codex — write this first
├── README.md                    # Problem, architecture, quickstart
├── requirements.txt
├── config.py
│
├── gateway/
│   ├── __init__.py
│   ├── server.py                # FastAPI app, routes
│   ├── proxy.py                 # Downstream forwarding
│   └── validation.py            # Envelope checks → E100/E102/E103
│
├── models/
│   ├── intent.py
│   ├── claim.py
│   ├── observation.py
│   └── attestation.py
│
├── oracle/
│   ├── __init__.py
│   ├── treasury.py              # Fiscal Data client
│   ├── tenors.py                # Tenor → CMT series mapping
│   └── cache.py                 # TTL cache
│
├── attest/
│   ├── __init__.py
│   ├── engine.py                # evaluate() — the interface contract
│   ├── signing.py               # Ed25519 + canonicalization
│   └── errors.py                # CUSTOS-Exxx taxonomy
│
├── claims/
│   ├── __init__.py
│   ├── registry.py
│   └── seed.json
│
├── demo/
│   ├── run_demo.py
│   ├── verify_attestation.py    # Standalone — imports nothing from gateway
│   └── mock_lender.py           # Trivial downstream to prove proxy works
│
└── tests/
    └── test_engine.py
```

---

## 16. Execution Timeline

Focused build window is 11:00 AM – 1:15 PM (2h 15m). Demos begin 1:15 PM.

| Time | Activity | Gate |
|---|---|---|
| 10:00–10:35 | Registration and briefing. **Write `AGENTS.md` and `seed.json` by hand during this.** | Context file exists before Codex starts |
| 10:35–11:00 | Codex walkthrough. Run one live `curl` against the Treasury API to confirm endpoint and response shape. | Real yield value obtained |
| 11:00–11:10 | Freeze `evaluate()` signature. Launch three worktrees with specs from sections 12.2–12.4. | All three running |
| 11:10–11:50 | Worktree B is critical path — supervise it. A and C run in parallel. | B returns correct verdicts against live data |
| 11:50–12:20 | Merge B → A. Get one end-to-end request working. | `POST /v1/intent` returns a real signed attestation |
| 12:20–12:45 | Merge C → A. All three demo scenarios produce correct verdicts. | Full demo path works once |
| **12:45** | **FEATURE FREEZE.** No new code. | — |
| 12:45–1:00 | Run the exact demo sequence three times. Fix only breakage. | Three consecutive clean runs |
| 1:00–1:15 | Finalize README, push, rehearse the demo aloud once. | Repo public, demo rehearsed |
| 1:15–1:45 | Demonstrations and judging | — |

**The 12:45 freeze is the single most important line in this document.** A working demo of a modest build beats a broken demo of an ambitious one, every time.

---

## 17. Cut List

If behind schedule, cut strictly in this order:

1. Fourth seed asset (backing-ratio path)
2. Downstream proxy — return the verdict without forwarding
3. `CUSTOS-E202` backing-ratio check
4. Signed BLOCK responses — sign ALLOW only
5. `GET /v1/assets/{asset_id}` diagnostic endpoint
6. Any web UI (do not start one if behind)

**Never cut:**

- **Live Treasury fetch.** Mocked data on both sides makes the whole thing a simulation and the demo collapses under one question.
- **Independent signature verification.** Without it, "cryptographically signed" is an unbacked assertion.

---

## 18. Known Limitations

State these proactively in the demo. Naming them is stronger than being caught by them.

1. **Claims are simulated, not read from chain.** v1 reads a seeded registry. Reading real ERC-20 metadata or an oracle contract is a v2 item requiring RPC integration.
2. **Yield plausibility is a proxy for NAV verification.** Issuer NAV feeds are not publicly accessible. Custos checks a claimed yield against live market rates for its tenor; it does not audit a fund's actual holdings.
3. **Single trusted attestor.** v1 is one gateway with one keypair. A production design needs multiple independent attestors with stake or threshold signatures, since a single attestor is itself a trust assumption.
4. **Ephemeral keys.** Keys regenerate on restart. Production requires persistent keys with a published DID document.
5. **No on-chain anchoring.** Attestations are off-chain artifacts. Anchoring their hashes on-chain (individually or Merkle-batched) is the natural next step.
6. **Thresholds are hand-set, not calibrated.** The 2% drift and 24h staleness figures are reasoned defaults, not empirically derived from incident data.

---

## 19. Roadmap Beyond the Hackathon

| Phase | Work |
|---|---|
| **v0.2** | Read claims from live chain state via RPC instead of a seeded registry |
| **v0.3** | Merkle-batched on-chain anchoring of attestation hashes for auditability at low gas cost |
| **v0.4** | Implement as a conforming ERC-8004 Validation Registry so any ERC-8004 agent can consume attestations natively |
| **v0.5** | Multi-attestor quorum with threshold signatures, removing the single-trusted-party assumption |
| **v0.6** | Expand beyond Treasuries: commodity-backed tokens (proof-of-reserve APIs), tokenized private credit (payment status feeds) |

---

## 20. Demo Narrative

Three minutes, six beats.

1. **Problem (30s).** Tokenized Treasuries are the largest RWA category on-chain and are now usable as DeFi collateral. Agents borrow against them autonomously. Existing agent-trust infrastructure checks whether the *agent* is allowed and whether the *agent* is creditworthy. Nothing checks whether the *asset* is still telling the truth.
2. **The gateway (20s).** Show the architecture. Integration is a config change: point the agent at Custos instead of the chain.
3. **Block on staleness (30s).** Fire an intent at `TKN-UST-3M-002`. Show `CUSTOS-E101`. The loan never reaches the lender.
4. **Block on drift (30s).** Fire at `TKN-UST-3M-003` — a claim updated an hour ago, so a staleness check would pass it. Show `CUSTOS-E201` with the claimed yield beside the **live Treasury figure fetched seconds ago**. This is the beat that proves the data is real.
5. **Allow and verify (30s).** Fire at `TKN-UST-3M-001`. Show the signed attestation. Switch terminals and run `verify_attestation.py` against it independently.
6. **Codex and roadmap (20s).** Three parallel worktrees — oracle, gateway, demo — built concurrently and merged inside the build window. Roadmap: on-chain claim reads, Merkle anchoring, ERC-8004 Validation Registry conformance.