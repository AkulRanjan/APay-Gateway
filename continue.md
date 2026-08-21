# Continue here — Custos Gateway session handoff

**Written:** 2026-08-21
**Repo:** `C:\Users\asus\AIP-Gateway` · branch `main` · 6 commits, **nothing from this session is committed**
**Read this first, then `docs/superpowers/plans/2026-08-21-custos-aip-phase-1.md`.**

---

## 1. What this project is

Custos is a **pre-transaction asset-truth gateway** for autonomous agents holding tokenized
U.S. Treasury claims. Before an agent borrows against, trades, or redeems a position, it sends
an intent to Custos. Custos cross-checks the asset's asserted **Claim** against a live
**Observation** of the Treasury par yield curve and returns either a cryptographically signed
ALLOW attestation or a structured BLOCK carrying a `CUSTOS-Exxx` code.

Three signals, short-circuiting in a fixed order so the returned code names the most
fundamental problem:

```
staleness_hours = (now − claim.last_attested_at) / 3600          > 24h  → claim is unmaintained
yield_drift     = |observed_bps − claimed_bps| / observed_bps    > 2%   → claim is recent but WRONG
backing_ratio   = claimed_backing_usd / (tokens × nav_per_token) < 1.0  → claim is internally inconsistent
```

It is **not** an audit of a fund's private books — issuer NAV feeds are not public. It checks
whether a claimed yield is plausible **against the live market for its tenor**. Keep that
precision in any external description; it is the difference between a defensible claim and an
indefensible one.

---

## 2. What happened this session

Three documents were produced. No code was written. No commits were made.

| Artifact | Lines | What it is |
|---|---|---|
| `ARCHITECTURE.md` | 1,845 | Full technical audit of Custos **as it exists today**, verified by execution |
| `docs/superpowers/specs/2026-08-21-custos-aip-architecture-design.md` | 659 | Approved design for rebuilding Custos in AIP's architectural image |
| `docs/superpowers/plans/2026-08-21-custos-aip-phase-1.md` | 4,814 | Phase 1 implementation plan — 15 tasks, 86 TDD steps, full code in every step |

The user approved the spec and the plan. **The next action is executing Phase 1.**

---

## 3. The goal, precisely

`architecture1.md` in the repo root is the **AIP (Agent Intent Protocol) documentation** — a
16-layer pre-execution authorization protocol SDK. It is byte-identical to `../aip/ARCHITECTURE.md`.

The user's directive, verbatim:

> *"I want the architecture to be same, do not use the AIP thing, custos is rebuilt in aip's
> image without any linkage or dependency on each other."*

So: **mirror AIP's architecture, do not import AIP.**

### Hard constraint — read this twice

The real AIP SDK (`aip-protocol` v0.4.0) exists in `../aip/`. **Do not import it, vendor it,
link to it, or add it as a dependency.** It is a blueprint, not a library. `tests/test_architecture.py`
(Task 15) enforces this programmatically. If you find yourself typing `import aip_protocol`,
you have misread the task.

### Layer mapping (spec §4.1)

| AIP layer | Custos module |
|---|---|
| Data Models | `custos_protocol/models.py` |
| Cryptography | `custos_protocol/crypto.py` |
| Canonical Serialization | `custos_protocol/canonical.py` |
| Agent Passport | `custos_protocol/passport.py` |
| Intent Envelope | `custos_protocol/envelope.py` |
| Verification Pipeline | `custos_protocol/verification.py` |
| Boundary Enforcement | `custos_protocol/boundaries.py` |
| **Intent Drift → Asset Truth** | **`custos_protocol/drift.py`** ← Custos's actual value slots in here |
| Attestation | `custos_protocol/attestation.py` |
| Delegation Chain | `custos_protocol/delegation.py` *(Phase 2)* |
| Revocation Store | `custos_protocol/revocation.py` |
| Trust Score | `custos_protocol/trust.py` *(Phase 2)* |
| Error Taxonomy | `custos_protocol/errors.py` |
| Shield / Observe / CLI | *(Phase 3)* |

`gateway/` becomes a thin FastAPI adapter. `claims/` and `oracle/` survive untouched behind
their existing `Claim | None` and `Observation | None` interfaces.

---

## 4. Phase plan (approach A — phased, each phase ends green)

- **Phase 1 — protocol core.** `errors`, `crypto`, `canonical`, `models`, `passport`,
  `envelope`, `boundaries`, `drift`, `attestation`, `revocation`, `verification` (steps 1–9,
  Tier 0/1), gateway rebuilt, tests and demos rewritten, `pyproject.toml`. **← YOU ARE HERE**
- **Phase 2 — trust layer.** `trust`, `delegation`, boundary predicate 4 (`E203` per-day),
  verification steps 10–11, Tier 2, `/v1/revocations` and `/v1/trust` routes.
- **Phase 3 — DX surfaces.** `shield`, `observe`, `cli`, `conformance/` vectors + runner.

`revocation.py` is in **Phase 1**, not Phase 2, because replay and revocation checks run at
every tier including Tier 0 — a Phase 1 gateway without them would ship two permanent holes.

---

## 5. How to resume

```bash
cd C:\Users\asus\AIP-Gateway
python -m pytest -q          # baseline: 12 passed  (bare `pytest` FAILS — Task 1 fixes that)
```

Read `docs/superpowers/plans/2026-08-21-custos-aip-phase-1.md`, then execute it with one of:

- **`superpowers:subagent-driven-development`** (recommended) — fresh subagent per task,
  review between tasks
- **`superpowers:executing-plans`** — inline batch execution with checkpoints

Tasks 1→12 build the SDK bottom-up; **the gateway does not come alive until Task 13.** Expect
the repo to be in a non-runnable intermediate state between Tasks 2 and 13. That is by design —
the test suite for each layer is green throughout.

---

## 6. Do NOT re-derive these — already verified by execution

Re-running this analysis costs time and tokens. It is all in `ARCHITECTURE.md` with evidence.

### Environment (measured)

```
Python 3.10.11 · Windows 11
pydantic 2.12.5 · fastapi 0.128.0 · cryptography 46.0.4 · httpx 0.28.1
python -m pytest -q  →  12 passed in 0.31s
pytest -q            →  3 collection errors (no pyproject.toml; Task 1 fixes it)
```

### Pydantic 2.12 serialization shapes (pinned by byte-exact tests)

- Aware-UTC datetime → `"2026-08-21T12:00:00Z"` (Z suffix; no fractional part when `microsecond == 0`)
- `Decimal("50000.00")` → the **string** `"50000.00"` — exactness survives the signature
- `float 500.0` → stays `500.0` through `json.dumps` — **this is why the whole-float→int rule exists**
- `None` → `null`, emitted not omitted
- `@context` sorts before all letters (`@` is `U+0040`)

### Measured performance

| Operation | Median |
|---|---|
| `evaluate()` full ALLOW path | 0.0064 ms |
| `sign()` (canonicalize + Ed25519) | 0.0333 ms |
| `POST /v1/intent` end-to-end, warm cache | 0.68 ms |
| `POST /v1/intent` BLOCK, no oracle call | 0.49 ms |
| **Treasury feed fetch** | **8,000–10,400 ms** |

The decision itself is free — the engine is 0.9% of the request. There is no performance
argument against adding checks.

### The live oracle is broken (`ARCHITECTURE.md` §18) — PARKED, do not fix during Phase 1

Two independent causes, each sufficient:

1. `oracle/treasury.py:16` points at `.../interest-rates/yield.xml`, which serves a legacy
   `QR_BC_CM` document with **no `<entry>` elements**. `parse_yield_curve` finds none and
   returns `None`. **The parser is correct** — against Treasury's OData/Atom feed it returns
   `(2026-08-20, 3.87)` on the first try. Only the URL constant is wrong.
2. Both feeds take 8–10 s against a 3 s timeout with one retry (~7 s wall, then `None`).

Net effect: default configuration returns `CUSTOS-E300` to **every** request. Fail-closed
behaviour is correct; availability is zero. Every demo that shows an ALLOW substitutes the
oracle. The fix is one line for the URL plus one for the timeout — but it is **deliberately
out of Phase 1 scope**, and `oracle/` keeps its interface so it can land independently at any
time.

Also verified: with a working oracle and today's curve, **all four seeded assets block**,
including the "healthy" one (claims 400 bps; 3M prints 387; drift 3.36% > 2%). That is what
`POST /v1/demo/sync` exists to correct.

---

## 7. Deliberate divergences from the AIP blueprint

The blueprint documents defects in its own implementation. Since we are writing fresh, these
are built correctly. **Do not "fix" them back toward the blueprint** — each is intentional and
recorded in the spec.

| # | Custos does | AIP does | Why |
|---|---|---|---|
| 1 | **Signature checked before replay** | Replay first | Otherwise an unauthenticated attacker burns a victim's nonce with a garbage envelope |
| 2 | **Revocation fails closed on stale data** | Returns `NOT_REVOKED`, fails open | The blueprint's own highest-severity finding: revoking an org stops working ~500 ms later |
| 3 | `local_only` store is **never stale** | n/a | Failing closed on a store with no upstream would be a self-inflicted outage |
| 4 | **FIFO nonce cache with time-based expiry** | `set` with arbitrary eviction | Arbitrary eviction leaves a probabilistic replay hole past the cap |
| 5 | **Risk-relative tier selection** (`amount / per_transaction > 0.5`) | Flat `amount > 100` | The flat rule inverts risk ordering — the blueprint says so itself |
| 6 | **`per_day` and `asset_classes` enforced** | Signed and ignored | A boundary that is signed but unenforced is a lie in the payload |
| 7 | **Delegation monotonicity enforced** *(Phase 2)* | Declared, never read | Same |
| 8 | **No `valid` field — `passed` is the single authority**, with a three-valued `checks` map | Both `valid` and `passed`, patched up at Tier 0 | Removes the documented trap; `NOT_RUN` becomes representable without lying |
| 9 | **`expires_at` required** | Nullable | A nullable expiry means an envelope that never expires |
| 10 | **Denials are signed too** | Only ALLOW signed | Otherwise a relying party cannot prove it was denied |
| 11 | **Non-finite floats rejected at the schema layer** | Normalizer crashes on them | — |
| 12 | **Encrypted private keys supported, file mode `0600`** | `NoEncryption()`, no chmod | — |

Two Phase-1-specific honesty rules:

- **An unregistered agent yields `CUSTOS-E100`** (`INVALID_SIGNATURE`) with detail
  `"No registered key for agent <id>; signature cannot be verified."` The taxonomy is fixed at
  30 codes and has no `UNKNOWN_AGENT`. An envelope whose signature cannot be validated is
  exactly an invalid signature, and it fails closed.
- **A Tier 2 envelope reports `tier_used = TIER_1`** in Phase 1. Claiming `TIER_2` while
  running Tier 1 checks would be a lie a relying party cannot detect.

---

## 8. Breaking changes Phase 1 introduces

- **The `custos/1` envelope is gone**, replaced by the JSON-LD-flavoured `CustosEnvelope`
  (`@context: https://custos.protocol/v1`, `@type: CustosEnvelope`, `protocol_version: 1.0.0`).
  Every test, demo and doc is rewritten in the same pass — there is no half-migrated state.
- **Every error code is renumbered** into the five-family shape. All eleven current codes
  survive semantically. The old→new table is in spec §16.2. Examples:
  `E101 CLAIM_STALE → E300`, `E201 YIELD_DRIFT → E301`, `E300 ORACLE_UNAVAILABLE → E500`.
- **`models/`, `attest/`, `gateway/validation.py` and `config.py` are deleted**, folded into
  `custos_protocol/` and `gateway/config.py`.
- **`POST /v1/demo/sync` moves behind `CUSTOS_DEMO_MODE=1`** — it is currently an
  unauthenticated state-mutation endpoint in the public OpenAPI schema.
- **`CUSTOS_FAIL_MODE` is deleted** — documented as `closed | open`, read by nothing.
- **`CUSTOS_DOWNSTREAM_TIMEOUT` is added** — the downstream proxy currently reuses the oracle
  timeout knob.

---

## 9. Open decisions awaiting the user

1. **Execution mode** — subagent-driven (recommended) or inline via `executing-plans`.
2. **`demo/live.html`** — Task 14 downgrades the browser demo's "Evaluate intent" button to
   `GET /v1/assets/{id}`, because a web page cannot hold a signing key safely and every
   envelope must now be signed. That is a real capability loss in the demo. Worth confirming
   before it is built.
3. **When to land the oracle P0** — independent of everything above; one line for the URL, one
   for the timeout, plus the live-shape test the original spec called for and nobody wrote.

---

## 10. Repo state right now

```
Untracked, uncommitted:
  ARCHITECTURE.md                                              ← audit of the CURRENT system
  architecture1.md                                             ← the AIP blueprint (input, do not edit)
  continue.md                                                  ← this file
  docs/superpowers/specs/2026-08-21-custos-aip-architecture-design.md
  docs/superpowers/plans/2026-08-21-custos-aip-phase-1.md

Unchanged from HEAD (be4a191):
  custos source, tests, demos — no code was modified this session
```

Nothing is committed because the user was on `main` and had not asked for commits. If you are
asked to commit, **branch first**.

---

## 11. Working agreements observed this session

- The user prefers being told what changed and why, concisely, with the reasoning visible.
- Do not commit or push unless explicitly asked.
- Do not spawn subagents unless asked. (`subagent-driven-development` for plan execution is
  the exception — the user picks it.)
- The superpowers workflow was followed: `brainstorming` → `writing-plans` → *(next: an
  execution skill)*. Both gates were approved by the user.
- Findings are reported plainly with evidence. Several claims in the repo's own docs did not
  survive execution; those are catalogued in `ARCHITECTURE.md` §19 and §22 rather than
  smoothed over.
