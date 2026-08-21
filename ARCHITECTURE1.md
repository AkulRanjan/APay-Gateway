# AIP — Agent Intent Protocol: Complete Technical Documentation

> A full read of the repository as it stands at commit `c33c6ab` (v0.4.0), covering
> every module, every data structure, every verification rule, the spec-vs-code
> divergences, the security model, measured performance, and the open-source /
> commercial split.
>
> Everything in this document was verified by reading the source and executing it —
> test runs, conformance runs, and micro-benchmarks are reproduced inline.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Identity & Provenance](#2-project-identity--provenance)
3. [Repository Map](#3-repository-map)
4. [Architecture at a Glance](#4-architecture-at-a-glance)
5. [Layer 1 — Data Models (the wire format)](#5-layer-1--data-models-the-wire-format)
6. [Layer 2 — Cryptography](#6-layer-2--cryptography)
7. [Layer 3 — Canonical Serialization (the interop core)](#7-layer-3--canonical-serialization-the-interop-core)
8. [Layer 4 — Agent Passport](#8-layer-4--agent-passport)
9. [Layer 5 — Intent Envelope](#9-layer-5--intent-envelope)
10. [Layer 6 — The Verification Pipeline](#10-layer-6--the-verification-pipeline)
11. [Layer 7 — Boundary Enforcement Semantics](#11-layer-7--boundary-enforcement-semantics)
12. [Layer 8 — Intent Drift Classifier](#12-layer-8--intent-drift-classifier)
13. [Layer 9 — Attestation](#13-layer-9--attestation)
14. [Layer 10 — Delegation Chain](#14-layer-10--delegation-chain)
15. [Layer 11 — Revocation Store](#15-layer-11--revocation-store)
16. [Layer 12 — Trust Score Engine](#16-layer-12--trust-score-engine)
17. [Layer 13 — Error Taxonomy](#17-layer-13--error-taxonomy)
18. [Layer 14 — Shield (enforcement DX)](#18-layer-14--shield-enforcement-dx)
19. [Layer 15 — Observe (observability DX)](#19-layer-15--observe-observability-dx)
20. [Layer 16 — CLI](#20-layer-16--cli)
21. [The Conformance Suite](#21-the-conformance-suite)
22. [The Test Suite](#22-the-test-suite)
23. [Examples & Demos](#23-examples--demos)
24. [The Documentation Site](#24-the-documentation-site)
25. [Measured Performance](#25-measured-performance)
26. [Spec ↔ Implementation Divergences](#26-spec--implementation-divergences)
27. [Security Model & Threat Analysis](#27-security-model--threat-analysis)
28. [Open Source ↔ Commercial Boundary](#28-open-source--commercial-boundary)
29. [Evolution (git history)](#29-evolution-git-history)
30. [Findings & Recommendations](#30-findings--recommendations)
31. [Glossary & Quick Reference](#31-glossary--quick-reference)

---

## 1. Executive Summary

**What this is.** AIP (Agent Intent Protocol) is a *pre-execution authorization protocol*
for autonomous AI agents, plus a reference Python SDK implementing it. The pitch is
"HTTPS for AI agents": before an agent performs a consequential action, it constructs a
**cryptographically signed declaration of what it is about to do**, and a verifier runs a
deterministic pipeline that either authorizes or rejects it — with a machine-readable
error code on rejection.

**The core insight.** API keys and OAuth authenticate the *caller*. RBAC authenticates the
*role*. Guardrails inspect *output*. None of them answer the question "is this specific
action, with these specific parameters, inside the mandate this agent was given?" — and
none of them can do it *before* the action fires. AIP's answer is: put the mandate
(the **boundary cage**) inside the signed message, and check the action against it.

**The four primitives.**

| Primitive | What it is | Where it lives |
|---|---|---|
| **Agent Passport** | DID identity + Ed25519 keypair + boundary cage + attestation | `aip_protocol/passport.py` |
| **Intent Envelope** | Signed declaration of `{who, authorized-by, what, allowed-what}` | `aip_protocol/envelope.py`, `models.py` |
| **Verification Pipeline** | Ordered, tier-gated sequence of checks producing accept/reject + error code | `aip_protocol/verification.py` |
| **Revocation + Trust** | Kill switch (instant) and earned reputation (behavioural) | `revocation.py`, `trust.py` |

**Two adoption surfaces sit on top of the protocol.** `@observe` (log everything, block
nothing, free) and `@shield` / `protect()` / `protect_agent()` (enforce). The deliberate
product design is that both create the *same* `AgentPassport` with the *same* DID, so
moving from visibility to enforcement is a one-decorator diff.

**State of the code (verified by execution).**

```
pytest tests/ -q          → 98 tests: 97 passed, 1 failed
                             (the failure is a timing assertion, not a logic bug —
                              §22 has the detail)
python conformance/run_conformance.py
                          → ALL 31 VECTORS PASSED (16.0ms)
```

Measured verification latency on this machine is **0.04 ms (Tier 0/HMAC) to 0.14 ms
(Tier 2)** — roughly an order of magnitude faster than the README's conservative
"<1ms / ~5ms / ~50-100ms" targets (§25).

**Maturity assessment.** The cryptographic core, canonical serialization, boundary engine,
replay detection and kill switch are real, tested, and cross-language-specified. The
*perimeter* features — attestation, delegation monotonicity, per-day monetary limits,
distributed revocation, trust persistence — range from partially implemented to
declared-only. §26 and §30 enumerate exactly which is which, because the README and RFC
currently claim several of them without qualification.

---

## 2. Project Identity & Provenance

| Fact | Value | Source |
|---|---|---|
| Package name | `aip-protocol` | `pyproject.toml` |
| Version | `0.4.0` | `pyproject.toml`, `aip_protocol/__init__.py:6` |
| Protocol name | AIP-1 | `RFC-001.md` |
| Python requirement | `>=3.10` (uses PEP 604 `X \| None`) | `pyproject.toml` |
| Build backend | `hatchling` | `pyproject.toml` |
| License | MIT, "Copyright (c) 2026 Korven" | `LICENSE` |
| Author metadata | Aniket Giri `<aniket@kyalabs.com>` | `pyproject.toml` |
| RFC authorship | "Korven (hello@korven.cc)" | `RFC-001.md`, `RFC-001-manifesto.md` |
| Repository | `github.com/theaniketgiri/aip` | README, RFC references |
| Product site | `aip.synthexai.tech` (also `korven.cc` in the docs site) | README, `cli.py:44` |
| Git branch | `master`, clean tree | `git status` |
| Console script | `aip = aip_protocol.cli:cli` | `pyproject.toml` |

**Naming layers to keep straight.** *AIP-1* is the protocol. *`aip-protocol`* is the Python
SDK. *Korven* is the brand ("Know Your Agent before it acts"). *Synthex AI / kyalabs* appear
as the commercial vehicle — `aip.synthexai.tech`, `mesh.synthexai.tech`, and API keys
prefixed `kya_`. The commercial layer is called **AIP Cloud** in the README and **the
Revocation Mesh** in the RFC.

**Runtime dependencies** (deliberately small — this is meant to be embeddable):

```
pydantic  >= 2.0     # models + validation + JSON mode serialization
cryptography >= 42.0 # Ed25519 (libsodium-grade, constant-time)
click     >= 8.0     # CLI
rich      >= 13.0    # CLI rendering
```

Dev extra: `pytest>=8.0`, `pytest-asyncio>=0.23`. **There is no network dependency in the
verification path** — this is a load-bearing claim of the design and it holds: nothing in
`verification.py`, `envelope.py`, `crypto.py`, `revocation.py` or `trust.py` opens a socket.
The only network code in the package is in `cli.py` (`aip status` / `aip watch` hitting
AIP Cloud over `urllib`).

---

## 3. Repository Map

```
aip/
├── aip_protocol/                  ← the SDK (the product)
│   ├── __init__.py                74 L   public API surface / re-exports
│   ├── models.py                 205 L   Pydantic wire format (the schema)
│   ├── crypto.py                 132 L   Ed25519 + HMAC + PEM/base64 key I/O
│   ├── errors.py                  95 L   23 AIP-Exxx codes + descriptions + exception
│   ├── passport.py               233 L   identity lifecycle: create/save/load
│   ├── envelope.py               200 L   envelope construction, tier auto-select, signing,
│   │                                     canonical serialization
│   ├── verification.py           513 L   THE PIPELINE + intent classifier + sub-checks
│   ├── revocation.py             209 L   kill switch store + nonce replay cache
│   ├── trust.py                  133 L   behavioural trust score engine
│   ├── shield.py                 413 L   one-liner enforcement API (protect/shield/protect_agent)
│   ├── observe.py                520 L   one-liner observability API (@observe + store)
│   └── cli.py                    626 L   click CLI: passport/sign/verify/revoke/inspect/
│                                         init/login/status/watch
│
├── conformance/                   ← cross-language proof-of-correctness
│   ├── vectors.json             2569 L   31 signed test vectors + key material + reference bytes
│   ├── generate_vectors.py       630 L   deterministic vector generator (fixed seeds)
│   ├── run_conformance.py        366 L   reference runner
│   ├── CANONICAL_SERIALIZATION.md 279 L  NORMATIVE byte-level serialization spec
│   └── README.md                 213 L   how to conform in another language
│
├── tests/
│   ├── test_aip.py               996 L   core protocol suite (13 classes)
│   └── test_observe.py           532 L   observability suite (9 classes)
│
├── examples/                      ← 8 runnable, dependency-free scripts
│   ├── 01_quickstart.py           protect() in 3 steps
│   ├── 02_protect_agent.py        wrap an existing object
│   ├── 03_shield_decorator.py     class decorator
│   ├── 04_full_pipeline.py        manual passport→envelope→sign→verify
│   ├── 05_kill_switch.py          revocation semantics
│   ├── 07_multi_agent.py          agent-to-agent, first_contact tier escalation
│   ├── 08_geo_restriction.py      geo boundary
│   └── 09_observe_agents.py       all 8 @observe features
│   (06_langchain.py is gitignored — it belonged to the commercial adapter)
│
├── demos/
│   ├── langchain_protected_tools/ 346 L  4 tools, per-tool boundaries, kill switch, reinstate
│   ├── crewai_financial_compliance/ 312 L 3 agents, selective revocation
│   └── interactive/app.py         578 L  FastAPI + embedded HTML dashboard (port 5050)
│
├── docs/index.html               957 L   GitHub Pages docs / marketing site
├── attack_demo.py                385 L   5 scripted attacks, all blocked (the "demo reel")
├── RFC-001.md                   1019 L   IETF-style normative specification
├── RFC-001-manifesto.md          225 L   narrative/positioning version of the RFC
├── README.md                     406 L   the front door
├── pyproject.toml / LICENSE / .gitignore / .dockerignore
```

**What `.gitignore` tells you about the shape of the business.** The ignore list is not
ordinary hygiene — its first block is labelled *"Commercial Product (PRIVATE — never push)"*
and excludes `kya_api/`, `mesh/`, `dashboard/`, `integrations/`, `sdks/`,
`aip_protocol/mesh.py`, `examples/06_langchain.py`, `Dockerfile`, `docker-compose.yml`,
`Caddyfile`, `*.pem`. So this repo is the deliberately-carved open core of a larger private
system (§28).

---

## 4. Architecture at a Glance

### 4.1 Module dependency graph

```
                         errors.py            (leaf: no internal deps)
                             ▲
                             │
                         models.py            (leaf+errors: the schema)
                             ▲
              ┌──────────────┼───────────────┐
              │              │               │
          crypto.py     passport.py      revocation.py      trust.py
         (leaf: no        ▲    ▲          (leaf)            (leaf)
        internal deps)    │    │              ▲                ▲
              ▲           │    │              │                │
              └───────────┤    │              │                │
                          │    │              │                │
                     envelope.py ─────────────┼────────────────┤
                          ▲                   │                │
                          │                   │                │
                    verification.py ──────────┴────────────────┘
                          ▲
              ┌───────────┴───────────┐
          shield.py                cli.py
              │
          observe.py (depends only on passport.py — deliberately NOT on verification)
```

Two things worth noticing:

1. **`observe.py` does not import `verification.py`.** Observability is structurally
   incapable of blocking a call. That is the whole point of the free tier — you cannot
   accidentally break production by adding `@observe`.
2. **`verification.py` is the only module that composes everything.** It is the choke point;
   everything else is a leaf or near-leaf. This is why the SDK stays embeddable.

### 4.2 The protocol dataflow

```
  ┌─────────────────────────── PRINCIPAL (human / org) ───────────────────────────┐
  │  did:web:acme-corp.com                                                        │
  │      │ delegates (DelegationLink: from → to, scope, monotonicity, expiry)      │
  │      ▼                                                                        │
  │  AGENT  did:web:acme-corp.com:agents:procurement-v1                           │
  │      ├── Ed25519 private key (never transmitted)                              │
  │      └── Boundary Cage: allowed / denied / $limits / geo / time / data scopes  │
  └───────────────────────────────────────────────────────────────────────────────┘
                                     │
             agent decides to act    │   create_envelope(passport, action, params)
                                     ▼
  ┌──────────────────────────── INTENT ENVELOPE ──────────────────────────────────┐
  │  @context, @type, protocol_version                                            │
  │  agent{id, version, runtime, attestation{...}}                                │
  │  principal{type, id, delegation_chain[]}                                      │
  │  intent{action, target, parameters{}}          ← WHAT IT WANTS                │
  │  boundaries{allowed, denied, monetary, geo, time, data}  ← ITS CAGE (SIGNED!) │
  │  verification_tier, entropy(nonce), ttl, issued_at, expires_at                │
  │  proof{type, created, verification_method, proof_purpose, proof_value}        │
  └───────────────────────────────────────────────────────────────────────────────┘
                                     │ sign_envelope(env, private_key)
                                     │   payload = canonical(env \ proof)
                                     ▼
  ┌────────────────────────── VERIFICATION PIPELINE ──────────────────────────────┐
  │ 1 version → 2 schema → 3 expiry → 3b nonce-format → 3c replay →               │
  │ 4 signature → 5 boundaries → 5b revocation ══╡ TIER 0 EXIT ╞══                │
  │ 6 attestation → 7 deep revocation ═══════════╡ TIER 1 EXIT ╞══                │
  │ 7b intent-drift → 7c delegation → 8 trust score ═══ TIER 2 EXIT ═══           │
  └───────────────────────────────────────────────────────────────────────────────┘
                                     │
                     VerificationResult{valid, signature_valid, within_boundaries,
                                        attestation_match, revocation{}, trust_score,
                                        tier_used, errors[AIP-Exxx], detail}
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                     EXECUTE ACTION        REJECT + audit code
```

**The load-bearing design decision:** the boundary cage travels *inside* the signed
envelope. A verifier does not need to look up a policy database to know what the agent was
allowed to do — the agent's own signature attests to its constraints. Tampering with the
cage invalidates the signature. This is what makes verification a local, zero-network,
sub-millisecond operation.

The trade-off, which the RFC is honest about and which §27 revisits: an agent that holds its
own private key can mint a passport with any cage it likes. AIP binds *action ↔ declared
mandate*, and binds identity to a DNS-controlled DID; it does not by itself prove that the
mandate was issued by the principal. That proof is what the delegation chain and the
(commercial) registry are for.

---

## 5. Layer 1 — Data Models (the wire format)

`aip_protocol/models.py` — every protocol message is a Pydantic v2 model. This file *is*
the schema.

### 5.1 Enumerations

```python
class VerificationTier(str, Enum):
    TIER_0 = "tier_0"   # HMAC / cached boundary proof   — target <1ms
    TIER_1 = "tier_1"   # Ed25519 + boundary assertion   — target ~5ms
    TIER_2 = "tier_2"   # full pipeline                  — target ~100-500ms

class AttestationMethod(str, Enum):
    SELF_REPORTED      = "self_reported"        # V0 — agent claims its own hash
    FRAMEWORK_REGISTRY = "framework_registry"   # V1 — framework signs the build
    TEE_HARDWARE       = "tee_hardware"         # V2 — SGX/SEV hardware attestation

class RevocationStatus(str, Enum):
    NOT_REVOKED = "not_revoked"
    REVOKED     = "revoked"
    SUSPENDED   = "suspended"
```

All three inherit `str`, so they serialize to plain JSON strings and compare equal to their
string values — deliberate, for cross-language wire compatibility.

Note `TEE_HARDWARE` is declared but nothing consumes it; and `RFC-001.md §4.4` lists a
different third method (`third_party_audit`). A small spec/code drift (§26).

### 5.2 Sub-models

| Model | Fields | Notes |
|---|---|---|
| `IntentClassifier` | `model="aip-classifier-v1"`, `confidence_threshold=0.95` (0..1) | Config only — the actual classifier (§12) is rule-based and **ignores both fields** |
| `Attestation` | `method`, `framework_id`, `build_hash`, `system_prompt_hash`, `registry_signature`, `intent_classifier` | Default `method` is `FRAMEWORK_REGISTRY` here, but `AgentPassport.create` overrides to `SELF_REPORTED` when no `framework_id` is passed |
| `MonetaryLimit` | `per_transaction≥0`, `per_day≥0`, `currency="USD"` | `per_day` is **stored but never enforced** (§11.2) |
| `TimeWindow` | `start`, `end` (datetimes) | Enforced |
| `Boundaries` | `allowed_actions[]`, `denied_actions[]`, `monetary_limit`, `data_access[]`, `geo_restriction`, `time_window` | `data_access` is **stored but never enforced** |
| `DelegationLink` | `from`(alias)→`from_id`, `to`(alias)→`to_id`, `scope`, `boundary_monotonicity=True`, `granted_at`, `expires_at` | `from`/`to` are Python keywords hence the aliases; `populate_by_name=True` allows both forms |
| `Principal` | `type="organization"`, `id`, `delegation_chain[]` | |
| `Proof` | `type="Ed25519Signature2020"`, `created`, `verification_method`, `proof_purpose="assertionMethod"`, `proof_value` | Modelled on W3C Data Integrity proofs. **`proof.type` is not validated during verification** — an envelope claiming a different suite is still verified as Ed25519 |
| `Intent` | `action`, `target=""`, `parameters{}` | `parameters` is free-form; `amount` is the only key the boundary engine interprets |
| `AgentIdentity` | `id` (auto `did:web:localhost:agents:<12 hex>`), `version="1.0.0"`, `runtime="aip-sdk/0.1.0"`, `attestation` | `runtime` is hardcoded at `0.1.0` while the package is `0.4.0` |

### 5.3 `IntentEnvelope` — the atomic unit

```python
class IntentEnvelope(BaseModel):
    context: str  = Field(default="https://aip.protocol/v1", alias="@context")
    type: str     = Field(default="IntentEnvelope",          alias="@type")
    protocol_version: str = "1.0.0"

    agent: AgentIdentity
    principal: Principal
    intent: Intent
    boundaries: Boundaries

    verification_tier: VerificationTier = TIER_1
    entropy: str = f"nonce:{uuid4().hex}"      # 38 chars
    ttl: int = 300                              # bounded 1..86400
    issued_at: datetime = now(utc)
    expires_at: datetime | None = None

    proof: Proof
    model_config = {"populate_by_name": True}
```

The JSON-LD-flavoured `@context` / `@type` aliases put AIP in the same idiom as W3C
Verifiable Credentials without pulling in a JSON-LD processor. They participate in the
signature (they sort first — `@` is `U+0040`, before all letters).

`ttl` is validated `1 ≤ ttl ≤ 86400`, but note **`expires_at` is what the verifier checks**;
`ttl` is only used by `create_envelope` to compute it. An envelope with `expires_at=None`
never expires (§26).

### 5.4 `VerificationResult` — the structured verdict

```python
class VerificationResult(BaseModel):
    valid: bool = False
    signature_valid: bool = False
    within_boundaries: bool = False
    attestation_match: bool = False
    revocation: RevocationCheck
    trust_score: float = 0.0        # 0..1
    tier_used: VerificationTier
    errors: list[AIPErrorCode] = []
    detail: str = ""

    @property
    def revoked(self)  -> bool: revocation.status != NOT_REVOKED
    @property
    def passed(self)   -> bool: valid AND signature_valid AND within_boundaries
                                AND attestation_match AND (not revoked)
```

**`valid` vs `passed` is a real distinction and a live trap.** The pipeline sets `valid=True`
at each tier exit, but on **Tier 0** it also force-sets `attestation_match=True` with the
comment *"N/A for Tier 0, mark as passed"* — precisely so `passed` doesn't return `False` for
a legitimately-accepted fast-path envelope. Most of the SDK's own call sites
(`shield.py`, the demos, the interactive app) branch on `result.valid`; the CLI and the
integration tests branch on `result.passed`. They agree today, but only because of that
manual patch-up.

`RevocationCheck` carries `{status, freshness, max_staleness_ms=500, confidence}` where
`confidence ∈ {"strong","weak"}` — `"weak"` meaning the answer was derived from stale data.
That field is where a significant fail-open behaviour hides (§15.4, §30).

---

## 6. Layer 2 — Cryptography

`aip_protocol/crypto.py` — a thin, honest wrapper over `cryptography`'s Ed25519. No custom
crypto is implemented, which is the correct decision.

### 6.1 Asymmetric (Ed25519, RFC 8032)

| Function | Behaviour |
|---|---|
| `generate_keypair()` | `Ed25519PrivateKey.generate()` → `(priv, pub)` |
| `sign_data(priv, bytes) -> str` | raw 64-byte signature, **base64url** encoded |
| `verify_signature(pub, bytes, sig_b64) -> bool` | never raises; returns `False` on any failure |
| `save_private_key` / `load_private_key` | PEM, PKCS8, **`NoEncryption()`** |
| `save_public_key` / `load_public_key` | PEM, SubjectPublicKeyInfo |
| `public_key_to_b64` / `b64_to_public_key` | raw 32-byte form, base64url — this is the passport-embedding format |

Two properties worth calling out:

- **Encoding is `urlsafe_b64` everywhere** (`-`/`_` alphabet, with `=` padding retained).
  Any second implementation must match this or every signature comparison fails. The
  conformance vectors pin it (`public_key_b64: "5zTqbCtiV95yNV5HKqBaTEh-a0Y8Ap7TBt8vAbVja1g="`).
- **`verify_signature` swallows everything**: `except (InvalidSignature, Exception): return False`.
  Safe for a verifier (fail-closed), but it also masks programming errors like passing a
  `str` where `bytes` is expected. The redundant `InvalidSignature` in that tuple is
  cosmetic.

**Private keys are written to disk unencrypted** (`NoEncryption()`), which directly
contradicts `RFC-001 §11.2` ("Private keys MUST be stored encrypted at rest"). `.gitignore`
excludes `*.pem` as compensation. See §30.

### 6.2 Symmetric (HMAC-SHA256, Tier 0 fast path)

```python
generate_hmac_key() -> bytes          # os.urandom(32) — 256-bit
hmac_sign(key, data) -> str           # base64url(HMAC-SHA256(key, data))
hmac_verify(key, data, sig) -> bool   # hmac.compare_digest — constant time
```

`compare_digest` is used correctly. What is *not* implemented is the key-establishment
handshake the RFC specifies (`§7.2`: X25519 agreement over the agent's Ed25519 key after a
successful Tier 1). In the SDK the HMAC key is simply a `bytes` argument the caller passes
to both signer and verifier — fine for a single trust domain, insufficient for the
cross-org Tier 0 the spec describes.

Also note the import placement: `hashlib` and `hmac` are imported *mid-file* at line 109
under a section banner rather than at the top. Harmless, unconventional.

---

## 7. Layer 3 — Canonical Serialization (the interop core)

This is the most important 20 lines in the repository. If two implementations disagree on
these bytes, every signature fails, and the protocol has no cross-language existence.

The rules are normative in `conformance/CANONICAL_SERIALIZATION.md` and implemented in
`envelope.py:111-154`.

### 7.1 The algorithm

```
getSignablePayload(envelope):
    1. data = envelope.model_dump(mode="json", by_alias=True, exclude={"proof"})
    2. data = normalize_floats(data)        # 500.0 → 500,  45.5 → 45.5
    3. json  = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    4. return json.encode("utf-8")
```

### 7.2 The five rules and why each exists

| # | Rule | Failure it prevents |
|---|---|---|
| 1 | **Exclude `proof`** | Circularity — you cannot sign your own signature |
| 2 | **Normalize whole floats to ints** (`500.0` → `500`) | Python emits `500.0`, JavaScript emits `500`. Different bytes → different signature → total interop failure. This is the single subtlest rule and it has its own conformance category |
| 3 | **Sort keys recursively, lexicographically** | Dict ordering differs across languages/versions. `@context` sorts before `@type` because `@` is `U+0040` |
| 4 | **No whitespace** (`separators=(",", ":")`) | Pretty-printing differences |
| 5 | **UTF-8 bytes** | Encoding ambiguity; strings escaped per RFC 7159 §7 |

Three more rules the spec states and the implementation obeys via Pydantic:

- **Datetimes are ISO-8601 with `Z`**, not `+00:00`, and no `.000` fractional part.
  (`mode="json"` gives this for free in Pydantic v2 — JavaScript implementations must strip
  `.000` manually.)
- **Nulls are emitted, never omitted.** `"expires_at":null` must appear. No
  `exclude_none`, no "skip empty" options.
- **Arrays preserve order** — `allowed_actions`, `denied_actions`, `data_access` and
  `delegation_chain` are *not* sorted.

### 7.3 The reference payload

`vectors.json._meta.reference_canonical_payload_hex` is a **1,146-byte** canonical encoding
of vector `A01`, published so a new implementation can bisect its serializer before it ever
touches a signature. Decoded, it begins:

```json
{"@context":"https://aip.protocol/v1","@type":"IntentEnvelope","agent":{"attestation":
{"build_hash":null,"framework_id":null,"intent_classifier":{"confidence_threshold":0.95,
"model":"aip-classifier-v1"},"method":"self_reported","registry_signature":null,
"system_prompt_hash":null},"id":"did:web:acme.com:agents:procurement-bot",
"runtime":"aip-sdk/0.1.0","version":"1.0.0"},"boundaries":{"allowed_actions":
["transfer_funds","read_invoice"],"data_access":[],"denied_actions":[],
"geo_restriction":null,"monetary_limit":{"currency":"USD","per_day":5000,
"per_transaction":500},"time_window":null},"entropy":"nonce:000...001",
"expires_at":null,"intent":{"action":"transfer_funds","parameters":{"amount":200,
"currency":"USD"},"target":"did:web:vendor.com:agents:billing"},
"issued_at":"2026-02-14T12:00:00Z", ...
```

Note `"per_day":5000` and `"amount":200` — rule 2 in action. Note `"expires_at":null`
present — the null rule. Note keys sorted at every level.

### 7.4 The gap in the float rule

`_normalize_floats` handles `float`, but the guard `obj == int(obj)` raises `OverflowError`
on `±inf` and `ValueError` on `NaN` — and the NaN check (`not (obj != obj)`) is evaluated
*after* that comparison, so it never gets the chance to help. In practice `json.dumps` would
emit non-standard `NaN`/`Infinity` anyway, so the real fix is rejecting non-finite floats at
the schema layer. Untested edge (§30).

---

## 8. Layer 4 — Agent Passport

`aip_protocol/passport.py` — the identity object. It is not a Pydantic model; it is a plain
class that *holds* models plus live key objects.

### 8.1 Construction

```python
AgentPassport.create(
    domain="acme.com", agent_name="procurement-bot",
    version="1.0.0", runtime="aip-sdk/0.1.0",
    principal_id=None, principal_type="organization",
    allowed_actions=[...], denied_actions=[...],
    monetary_limit_per_txn=0.0, monetary_limit_per_day=0.0, currency="USD",
    data_access=[...], framework_id=None, system_prompt_hash=None,
)
```

What it does, in order:

1. `agent_name` defaults to `agent-<8 hex>`.
2. **DID synthesis:** `did:web:{domain}:agents:{agent_name}`. Principal defaults to
   `did:web:{domain}`.
3. Generates a fresh Ed25519 keypair.
4. Builds `AgentIdentity` with attestation `FRAMEWORK_REGISTRY` **iff** `framework_id` was
   supplied, else `SELF_REPORTED`.
5. Builds a `Principal` with a **single auto-generated delegation link**
   `principal → agent`, scope `"default"`, `boundary_monotonicity=True`, no expiry.
6. Builds `Boundaries` from the flat kwargs.

Step 5 is why Tier 2 delegation validation passes out of the box: every passport ships with
a well-formed one-hop chain.

### 8.2 Persistence

`save(dir)` writes three files:

```
agent_passport/
├── passport.json   # identity + principal(by_alias) + boundaries + public_key(b64)
├── private.pem     # PKCS8, UNENCRYPTED
└── public.pem      # SubjectPublicKeyInfo
```

`load(dir)` reconstructs, with a documented key-resolution precedence:
`private.pem` (derives public from private) → `public.pem` → `passport.json["public_key"]`.
This gives you a natural **verifier-only passport**: ship `passport.json` without the PEMs
and the loaded object can verify but not sign (`.private_key` raises
`ValueError("No private key loaded — passport may be public-only")`).

`to_dict()` is the same payload minus the private key — safe to log or transmit.

**Gap:** `save()` does not `chmod 0600` the private key (the CLI *does* do this for its
credentials file, so the pattern exists in the codebase — it just wasn't applied here).

---

## 9. Layer 5 — Intent Envelope

`aip_protocol/envelope.py`.

### 9.1 `create_envelope(...)` and automatic tier selection

If the caller doesn't pin a tier, `_auto_select_tier` decides. The rules, verbatim:

```python
if cross_org or first_contact:            return TIER_2
if isinstance(amount,(int,float)) and amount > 100:  return TIER_2
if action in {"transfer_funds","delete","modify_payroll","admin"}: return TIER_1
return TIER_0
```

| Situation | Selected tier |
|---|---|
| Cross-org or first contact | **Tier 2** |
| `parameters["amount"] > 100` | **Tier 2** |
| Action in the hardcoded sensitive set | **Tier 1** |
| Everything else | **Tier 0** |

**This is where the implementation and the specification part ways most consequentially.**
`RFC-001 §5.3` defines escalation *relative to the agent's own limits* — "amount > 50% of
limit → tier_2", "amount < 10% of limit → tier_0". The code uses a flat, currency-blind
`> 100` and ignores `boundaries` entirely (the parameter is accepted and unused). Concretely:
an agent with a `$1,000,000` limit moving `$101` gets full Tier 2 treatment; an agent with a
`$50` limit moving `$99` gets Tier 0 — the opposite of the intended risk ordering. The
sensitive-action set is also a closed literal, so `wire_transfer`, `refund`, `deploy`,
`grant_access` all fall through to Tier 0.

Practical consequence: **a low-risk-looking action defaults to Tier 0, which skips
attestation, intent-drift, delegation and trust entirely.** Revocation and boundaries still
run (that part is correct and conformance-tested), but the semantic checks silently do not.
For production use, pin `tier=` explicitly.

Default `ttl=300s`; `expires_at = issued_at + ttl` is computed here (and *only* here — a
hand-built envelope has `expires_at=None` and never expires).

### 9.2 `sign_envelope(envelope, private_key, verification_method="")`

1. `payload = _get_signable_payload(envelope)` (§7)
2. `signature = sign_data(private_key, payload)`
3. Builds `Proof(type="Ed25519Signature2020", created=now,
   verification_method=verification_method or f"{principal.id}#keys-1",
   proof_purpose="assertionMethod", proof_value=signature)`
4. Returns `envelope.model_copy(update={"proof": proof})` — **immutable style**, the input
   envelope is not mutated.

Because `proof` is excluded from the payload, `proof.created` and `verification_method` are
*not covered by the signature*. An attacker can rewrite them freely. They're advisory
metadata; nothing in the pipeline reads them.

### 9.3 Helpers

- `envelope_to_json(env, pretty=True)` / `envelope_from_json(str)` — round-trip via aliases.
- `envelope_hash(env)` — SHA-256 hex of the canonical payload. Useful as an idempotency key
  or audit-log anchor. Deterministic and tested.

---

## 10. Layer 6 — The Verification Pipeline

`aip_protocol/verification.py:124` — `verify_intent(...)`. This is the protocol.

### 10.1 Full signature

```python
verify_intent(
    envelope: IntentEnvelope,
    public_key: Ed25519PublicKey,
    revocation_store: RevocationStore | None = None,   # default singleton if None
    trust_engine:     TrustScoreEngine | None = None,  # default singleton if None
    min_trust_score:  float = 0.0,                     # 0 = accept all
    registered_frameworks: set[str] | None = None,     # None = skip framework check
    hmac_key: bytes | None = None,                     # enables the Tier 0 fast path
    known_model_hashes:  dict[str,str] | None = None,  # framework_id → expected build hash
    known_prompt_hashes: dict[str,str] | None = None,  # agent_id     → expected prompt hash
    request_geo: str | None = None,                    # ISO-3166-1 alpha-2 of the caller
    max_revocation_staleness_ms: int | None = None,    # default 500
) -> VerificationResult
```

Two module-level singletons (`_default_revocation_store`, `_default_trust_engine`) exist for
convenience. **They are process-global mutable state** — in a multi-tenant server you must
pass explicit instances or agents from different tenants will share a nonce cache and a trust
history.

### 10.2 The steps, exactly as implemented

| # | Step | Runs at | On failure | Notes |
|---|---|---|---|---|
| 1 | `VERSION_CHECK` | all | `AIP-E104` | `protocol_version ∈ {"1.0.0"}` |
| 2 | `SCHEMA_CHECK` | all | `AIP-E103` | non-empty `intent.action`, non-empty `agent.id`. Pydantic did the structural work at parse time |
| 3 | `EXPIRY_CHECK` | all | `AIP-E101` | only if `expires_at is not None`; naive datetimes coerced to UTC. **No clock-skew grace** despite RFC §14.2 |
| 3b | `NONCE_VALIDATION` | all | `AIP-E105` | `len(entropy) ≥ 38` — i.e. `"nonce:"` + 32 hex. Length only; charset not validated |
| 3c | `REPLAY_CHECK` | all | `AIP-E102` | `store.check_nonce()` — **consumes the nonce as a side effect** |
| 4 | `SIGNATURE_CHECK` | all | `AIP-E100` | HMAC **iff** `tier==TIER_0 and hmac_key is not None`, else Ed25519 |
| 5 | `BOUNDARY_CHECK` | all | `AIP-E2xx` | also calls `trust.record_violation()` |
| 5b | `REVOCATION_CHECK` (fast) | **all incl. Tier 0** | `AIP-E400` / `E401` | the kill switch — deliberately *not* tier-gated |
| — | **TIER 0 EXITS HERE** | | | sets `valid=True`, `attestation_match=True`, clears errors |
| 6 | `ATTESTATION_VERIFY` | T1, T2 | `AIP-E300/301/302` | all three checks are opt-in via kwargs |
| 7 | `REVOCATION_DEEP` | T1, T2 | `AIP-E400` / `E401` | adds freshness/staleness + principal revocation |
| — | **TIER 1 EXITS HERE** | | | |
| 7b | `INTENT_DRIFT` | T2 | `AIP-E303` | rule-based classifier; records a violation |
| 7c | `DELEGATION_CHECK` | T2 | `AIP-E403` | continuity + endpoints + expiry |
| 8 | `TRUST_SCORE_CHECK` | T2 | `AIP-E404` | only if `min_trust_score > 0` **and** the agent has history |
| — | **TIER 2 EXITS HERE** | | | `detail="Tier 2 full: all 8 verification checks passed"` |

Failure is **fail-fast**: `_fail()` sets `valid=False`, attaches `errors` + `detail`, returns
immediately. No step after a failure executes. Note this means `errors` usually holds
exactly one code — except `_check_boundaries`, which accumulates *all* boundary violations
before returning, so a single envelope can legitimately come back with
`[ACTION_DENIED, MONETARY_LIMIT, GEO_RESTRICTION]`.

### 10.3 Ordering divergence from the RFC

`RFC-001 §6.1` specifies replay before signature and lists 12 numbered steps; the code also
does replay before signature (`3c` then `4`) — they agree on order. But the code's
*nonce-format* check (3b) has no RFC step number, and the RFC's numbering (1–12) never
matches the code's comments (1–8 with letter suffixes). The README's diagram is a third
numbering. All three describe the same pipeline; only the labels differ.

The security-relevant consequence of replay-before-signature: **an unauthenticated attacker
can burn nonces.** Submitting a garbage envelope carrying a victim's nonce consumes it from
the cache before the signature is ever checked, so the legitimate envelope bearing that nonce
is later rejected as a replay. Checking the signature first would close this. (Bounded
impact — the attacker must know a nonce that hasn't been submitted yet — but it's a real
ordering trade-off worth documenting.)

---

## 11. Layer 7 — Boundary Enforcement Semantics

`verification.py:324` — `_check_boundaries(envelope, request_geo)`. This is what actually
stops the money.

### 11.1 The exact predicates

```python
# 1. Deny list (checked first — deny wins)
if action in boundaries.denied_actions:            → ACTION_DENIED     (E201)

# 2. Allow list (only enforced if non-empty)
if boundaries.allowed_actions and action not in boundaries.allowed_actions:
                                                   → ACTION_NOT_ALLOWED (E200)

# 3. Monetary (per-transaction only)
amount = intent.parameters.get("amount")
if amount is not None and isinstance(amount,(int,float)):
    if monetary_limit.per_transaction > 0 and amount > per_transaction:
                                                   → MONETARY_LIMIT     (E202)

# 4. Time window
if boundaries.time_window and not (start <= now <= end):
                                                   → TIME_WINDOW_VIOLATION (E203)

# 5. Geo (only when the verifier supplies request_geo)
if boundaries.geo_restriction and request_geo:
    allowed = {g.strip().upper() for g in geo_restriction.split(",")}
    if request_geo.upper() not in allowed:         → GEO_RESTRICTION    (E204)
```

### 11.2 The semantics you must internalise

| Behaviour | Consequence |
|---|---|
| **Empty `allowed_actions` = allow everything** | A passport created with no actions is unconstrained on the action axis. Deny-by-default only applies once the list is non-empty |
| **`per_transaction = 0` means "no limit", not "no money"** | Verified experimentally: `protect(f, limit=0)` happily passes `amount=1_000_000_000`. The CrewAI demo's read-only agents use `limit=0` — correct there (they can't move money because `trade`/`transfer_funds` are on their deny lists), but the idiom is a footgun |
| **Negative amounts always pass** | `amount > limit` is false for `-50`. Conformance vector `G02` enshrines this as intended ("refund"). But a system treating negatives as credits has an unguarded path |
| **Only `parameters["amount"]` is inspected** | `{"value": 15000}`, `{"total": 15000}`, `{"amount_usd": 15000}` are invisible to the monetary check. There is no currency reconciliation either — a `per_transaction` in USD is compared to whatever number `amount` holds |
| **Geo is only checked if the verifier passes `request_geo`** | The boundary is inert unless the *caller* supplies the geography. AIP cannot determine it |
| **`geo_restriction` is a comma-separated list**, despite the RFC and docstrings describing it as a single ISO code | `"US,CA,GB"` works; the model type is just `str` |
| **`data_access` is never checked** | Declared in the cage, ignored by the engine |
| **`per_day` is never checked** | Declared, stored, serialized into the signed payload, never enforced — the rolling-window accounting doesn't exist. `RFC §16.5` acknowledges this as an open question for *distributed* verifiers, but it isn't enforced locally either |

### 11.3 Where the boundary result goes

On failure, `trust.record_violation(agent_id)` fires *before* returning, so a rejected
envelope permanently degrades the agent's trust score. That's the intended feedback loop —
and it's also an abuse vector, since anyone who can get an envelope submitted on an agent's
behalf can drive its score down. Trust is per-verifier and local, which bounds the blast
radius.

---

## 12. Layer 8 — Intent Drift Classifier

`verification.py:54-119`. Tier 2 only. Described in marketing as a "semantic classifier"; in
reality it is a **hand-written taxonomy with prefix matching**. The code is honest about this
("This is the V1 lightweight classifier. V2 would use embeddings").

### 12.1 The taxonomy

10 groups, ~60 actions:

| Group | Members |
|---|---|
| `financial` | transfer_funds, refund, charge, pay, invoice, billing, payment, withdraw, deposit |
| `data_read` | read, read_data, read_invoice, read_ticket, view, list, get, fetch, query, search |
| `data_write` | write, write_data, create, update, modify, edit, patch, upsert |
| `data_delete` | delete, remove, purge, drop, destroy, erase |
| `notification` | send_notification, send_email, notify, alert, send_message, broadcast, send |
| `admin` | admin, configure, modify_payroll, access_hr_records, manage_users, set_permissions |
| `order` | create_order, update_shipping, send_invoice, fulfill, ship, track |
| `support` | respond_ticket, escalate, resolve, close_ticket, assign |
| `report` | generate_report, analyze, summarize, export, dashboard |
| `account` | verify_account, authenticate, register, login, logout, reset_password |

A reverse index `_ACTION_TO_GROUP` is built at import time.

### 12.2 The algorithm

```
_classify_action_group(action):
    exact match in index?                    → that group
    else: longest-prefix match (case-insensitive, keys sorted by length desc)
    else: None

_check_intent_drift(envelope):
    if not allowed_actions:        return True   # nothing to compare against
    if action in allowed_actions:  return True   # exact match always wins
    group = classify(action)
    if group is None:              return False  # unknown → treated as drift
    return any(classify(a) == group for a in allowed_actions)
```

The rule: **an action not in the allowlist is tolerated only if it belongs to the same
semantic family as something that is.**

### 12.3 Known weaknesses — including a dead path

- **Ambiguous prefixes collide.** `send_invoice` is in `order` but `send` is in
  `notification`; `read_invoice` is `data_read` while `invoice` is `financial`.
  Longest-prefix ordering resolves these deterministically, but the results surprise —
  `"sender_verify"` matches prefix `send` → `notification`.
- **Unknown verbs are always drift.** Any domain-specific action (`rebalance_portfolio`,
  `provision_cluster`) classifies as `None` → drift → `AIP-E303`.
- **The taxonomy is not extensible.** No registration API, no config — a module-level literal.
- **`IntentClassifier.model` / `confidence_threshold` are decorative.** They're serialized
  into every signed envelope (visible in the reference bytes in §7.3) but no code reads them.
- **The rejecting branch is effectively unreachable through `verify_intent`.** Trace the
  ordering: step 5 already rejects any action absent from a non-empty allowlist, and
  `_check_intent_drift` returns `True` immediately both when the allowlist is empty and when
  the action is in it. So by the time step 7b runs, the only reachable outcomes are `True`.
  The drift tests in `TestIntentClassifier` call `_check_intent_drift` directly rather than
  through the pipeline (except `test_tier2_flags_intent_drift`, which mutates the boundaries
  after passport creation to construct the otherwise-unreachable state). Genuine dead-path
  finding (§30).

---

## 13. Layer 9 — Attestation

`verification.py:368` — `_check_attestation(...)`. Tier 1+ only. All three checks are
**opt-in**: if the verifier passes nothing, attestation trivially passes.

| Check | Fires when | Error |
|---|---|---|
| Framework registry | `attestation.method == "framework_registry"` **and** `registered_frameworks is not None` **and** `framework_id not in registered_frameworks` | `AIP-E302` |
| Model/build hash | `known_model_hashes` given **and** an entry exists for this `framework_id` **and** `build_hash` is set **and** they differ | `AIP-E300` |
| Prompt hash | `known_prompt_hashes` given **and** an entry exists for this `agent_id` **and** `system_prompt_hash` is set **and** they differ | `AIP-E301` |

**What attestation is *not*, in this implementation.** `Attestation.registry_signature` is
declared in the model but never verified — nothing checks that the framework actually signed
the build hash. So attestation here is a **self-declared value compared against a
verifier-supplied allowlist**, not a chain of trust. A compromised agent simply omits
`build_hash` (it's `None` by default) and every hash check short-circuits to pass.

The RFC is aware of this: `§4.4` positions `self_reported` as V0, `framework_registry` as V1
(framework signs the build), `tee_hardware` as V2. Only the *shape* of V1 exists; the
signature verification does not.

Field-name drift: the RFC calls it `model_hash`, the model calls it `build_hash`. A
TypeScript implementation following the RFC would produce a non-matching canonical payload.

---

## 14. Layer 10 — Delegation Chain

`verification.py:403` — `_check_delegation(...)`. Tier 2 only. All failures are `AIP-E403`.

### 14.1 What is checked

1. **Empty chain** → valid only if `principal.id == agent.id` (self-sovereign agent).
2. **Chain starts at the principal**: `chain[0].from_id == principal.id`.
3. **Chain ends at the agent**: `chain[-1].to_id == agent.id`.
4. **Continuity**: for each adjacent pair, `chain[i].to_id == chain[i+1].from_id`.
5. **Expiry**: no link may have `expires_at` in the past (naive datetimes coerced to UTC).

A correct, complete linked-list validation.

### 14.2 What is *not* checked

- **Boundary monotonicity.** `DelegationLink.boundary_monotonicity` defaults to `True` and is
  serialized into every signed envelope, but **no code reads it** (verified: only two
  references in the package, both writes, in `models.py` and `passport.py`). The RFC makes
  this a MUST in two places (`§4.5`, `§6.2 step 11`). This is the largest spec-vs-code gap:
  the property that a sub-agent cannot exceed its delegator's authority is documented,
  defaulted-on, wire-serialized — and unenforced.
- **Signatures on links.** A delegation link is unsigned data inside an envelope signed by
  the agent. The agent can therefore fabricate its own delegation chain. Nothing proves the
  principal actually granted the scope.
- **`scope`** is never compared to the requested action.
- **Depth limits.** `RFC §16.2` recommends max 5 levels; no limit is enforced.
- **`granted_at`** is never validated (a link "granted" in the future passes).

---

## 15. Layer 11 — Revocation Store

`aip_protocol/revocation.py` — the kill switch and the replay cache in one thread-safe
object.

### 15.1 Record shape

```python
RevocationRecord = NamedTuple(
    agent_id, reason, revoked_at, revoked_by,
    scope,            # "global" | "scoped" (never interpreted)
    suspended_until,  # None ⇒ permanent revocation; datetime ⇒ suspension
)
```

The permanent/temporary distinction is encoded purely by `suspended_until is None`.

### 15.2 API

| Method | Behaviour |
|---|---|
| `revoke(agent_id, reason, revoked_by, scope)` | permanent; bumps `_last_sync` |
| `suspend(agent_id, duration_seconds=1800, reason, revoked_by="circuit_breaker")` | temporary |
| `is_revoked(agent_id)` | `True` for both states; **lazily deletes expired suspensions** |
| `is_suspended(agent_id)` | distinguishes suspension from revocation |
| `reinstate(agent_id)` | removes the record; returns whether one existed |
| `get_record(agent_id)` | the raw record |
| `rehydrate(records: list[dict]) -> int` | restore from a DB after restart; parses ISO strings, **skips already-expired suspensions**; sets `_last_sync` |
| `touch_sync()` / `last_sync_time` | freshness bookkeeping |
| `check_nonce(nonce) -> bool` | `True` if new (and records it); `False` on replay |
| `clear_nonces()` | flush the cache |
| `revocation_count` | size |

All mutating paths hold a `threading.Lock`. The design intent (per the module docstring) is
that this is the local cache of a distributed **Revocation Mesh** — hot path via push, cold
path via DB rehydration.

### 15.3 The nonce cache

```python
MAX_NONCE_CACHE = 100_000
if len(self._nonce_cache) >= MAX_NONCE_CACHE:
    for _ in range(MAX_NONCE_CACHE // 10):
        self._nonce_cache.pop()     # set.pop() — arbitrary element
```

- It's a **`set`, so eviction is arbitrary, not LRU/FIFO**. The comment admits this
  ("set is unordered, so just discard some"). A *recent* nonce can be evicted while an
  ancient one survives, so replay protection has a probabilistic hole past 100k nonces.
- There is **no time-based expiry.** `RFC §10.2` requires retention ≥ max TTL and *permits*
  eviction after that; the implementation evicts by pressure only — below the cap it never
  forgets (unbounded retention of stale nonces), above it forgets randomly.
- The RFC asks for ≥1,000,000 concurrent nonces; the cap is 100,000 (10× lower).

### 15.4 Freshness — and a real fail-open

`_check_revocation` (the *deep* Tier 1/2 check) does this first:

```python
staleness_ms = (now - store.last_sync_time).total_seconds() * 1000
if staleness_ms > max_staleness_ms:          # default 500ms
    return RevocationCheck(status=NOT_REVOKED, confidence="weak", ...)
```

**When data is stale it returns NOT_REVOKED and verification proceeds.** It does not emit
`AIP-E501` (that code is never raised anywhere in the SDK), and the `confidence="weak"`
signal is never consulted by `verify_intent`. `RFC §8.4` says a verifier *SHOULD* return
`AIP-E501` in exactly this case.

Because `_last_sync` is set at construction and only refreshed on mutation, **a store that
hasn't been touched for 500 ms is permanently "stale"** — the normal state of any
long-running verifier.

Does the kill switch still work? For **agents, yes** — step 5b (`store.is_revoked(agent.id)`)
runs at every tier and is *not* staleness-gated. For **principals, no.** Principal revocation
(`store.is_revoked(principal.id)`) exists only inside the stale-gated deep check. Verified
experimentally:

```
A) principal revoked, store fresh  → valid: False  ['AIP-E400']   status: revoked
B) principal revoked, store stale  → valid: True   []             status: not_revoked, confidence: weak
C) agent     revoked, store stale  → valid: False  ['AIP-E400']   (kill switch holds)
```

So **revoking an organisation stops working ~500 ms after you revoke it**, unless something
else keeps mutating the store. This is the highest-severity finding in the audit (§30).

Related: when the principal *is* caught, the code returns `RevocationStatus.REVOKED`, which
`verify_intent` maps to `AIP-E400 AGENT_REVOKED` — so the dedicated `AIP-E402
PRINCIPAL_REVOKED` code is never emitted either.

---

## 16. Layer 12 — Trust Score Engine

`aip_protocol/trust.py` — "a credit score for agents — earned, not assigned."

### 16.1 State

```python
@dataclass
class AgentHistory:
    agent_id; total_intents=0; successful_intents=0; boundary_violations=0
    revocation_count=0; attestation_changes=0; delegation_depth=1
    first_seen; last_seen
```

Recorded by: `record_success` (on every tier's successful exit), `record_violation` (on
boundary failure and on intent drift), `record_revocation` and `record_attestation_change`
(manual — nothing in `verify_intent` calls them; `attack_demo.py` calls `record_revocation`
explicitly).

### 16.2 The formula

```
T(a) = 0.35·completion_rate
     + 0.25·(1 − violation_rate)
     + 0.15·max(0, 1 − 0.30·revocations)
     + 0.10·max(0, 1 − 0.15·attestation_changes)
     + 0.05·max(0, 1 − 0.20·(delegation_depth − 1))
     + 0.10·min(1, total_intents / 100)          ← age bonus
```

clamped to `[0,1]`, rounded to 4 dp. `total_intents == 0` returns exactly `0.0`.

### 16.3 Worked example

A brand-new agent with one clean verification:
`completion=1, violation_score=1, revocation=1, attestation=1, depth=1, age=0.01`
→ `0.35 + 0.25 + 0.15 + 0.10 + 0.05 + 0.001 = 0.901`.

That's the shape of the curve: **the first success buys 0.90; the remaining 0.10 is earned
slowly across 100 interactions.** Conversely one violation in ten interactions costs
`0.25 × 0.1 = 0.025` from the violation term, plus whatever the completion term loses.

### 16.4 Properties and caveats

- **"Bayesian" is a misnomer.** README, manifesto and docs site all call it a Bayesian
  reputation model; it is a fixed-weight linear combination with no priors, no posterior
  update and no uncertainty representation. Accurate description: *weighted behavioural score*.
- **Local, not global.** Each verifier keeps its own histories. `RFC §16.1` lists cross-org
  trust propagation as an open question.
- **In-memory only.** History dies with the process — consistent with the README listing
  "Persistent Trust Scores" as an AIP Cloud feature.
- **The gate is permissive by default.** `verify_intent` enforces `min_trust_score` only at
  Tier 2, only when `min_trust_score > 0`, and only when `history.total_intents > 0` — so
  brand-new agents always pass (matching `RFC §9.3`).
- **`delegation_depth` is never derived from the envelope.** `get_or_create` defaults it to 1
  and `verify_intent` never passes the actual chain length, so the depth penalty is
  permanently inert.
- **`meets_threshold()` exists but `verify_intent` doesn't call it** — it re-implements the
  comparison inline with different semantics.

---

## 17. Layer 13 — Error Taxonomy

`aip_protocol/errors.py`. **23 codes** (README and manifesto both say 22 — verified by
enumerating `AIPErrorCode`), each with a human description in `ERROR_DESCRIPTIONS`, plus an
`AIPError` exception with `.to_dict()` for structured API responses.

| Code | Name | Emitted at | Live? |
|---|---|---|---|
| `AIP-E100` | `INVALID_SIGNATURE` | step 4 | ✅ |
| `AIP-E101` | `EXPIRED_ENVELOPE` | step 3 | ✅ |
| `AIP-E102` | `REPLAY_DETECTED` | step 3c | ✅ |
| `AIP-E103` | `SCHEMA_INVALID` | step 2 | ✅ |
| `AIP-E104` | `VERSION_UNSUPPORTED` | step 1 | ✅ |
| `AIP-E105` | `NONCE_INVALID` | step 3b | ✅ (**missing from RFC §12.2**) |
| `AIP-E200` | `ACTION_NOT_ALLOWED` | boundary | ✅ |
| `AIP-E201` | `ACTION_DENIED` | boundary | ✅ |
| `AIP-E202` | `MONETARY_LIMIT` | boundary | ✅ (per-txn only) |
| `AIP-E203` | `TIME_WINDOW_VIOLATION` | boundary | ✅ |
| `AIP-E204` | `GEO_RESTRICTION` | boundary | ✅ (needs `request_geo`) |
| `AIP-E300` | `MODEL_HASH_MISMATCH` | attestation | ✅ opt-in |
| `AIP-E301` | `PROMPT_HASH_MISMATCH` | attestation | ✅ opt-in |
| `AIP-E302` | `FRAMEWORK_UNREGISTERED` | attestation | ✅ opt-in |
| `AIP-E303` | `INTENT_DRIFT` | Tier 2 | ⚠️ effectively unreachable (§12.3) |
| `AIP-E400` | `AGENT_REVOKED` | steps 5b, 7 | ✅ |
| `AIP-E401` | `AGENT_SUSPENDED` | steps 5b, 7 | ✅ |
| `AIP-E402` | `PRINCIPAL_REVOKED` | — | ❌ **never emitted** (principal revocation reports E400) |
| `AIP-E403` | `DELEGATION_INVALID` | Tier 2 | ✅ (5 sites) |
| `AIP-E404` | `TRUST_SCORE_LOW` | Tier 2 | ✅ conditional |
| `AIP-E500` | `MESH_UNAVAILABLE` | — | ❌ never emitted (belongs to the commercial mesh) |
| `AIP-E501` | `REVOCATION_STALE` | — | ❌ **never emitted** despite the staleness path existing (§15.4) |
| `AIP-E502` | `HANDSHAKE_TIMEOUT` | — | ❌ never emitted (Tier 0 key exchange unimplemented) |

**19 of 23 codes are live.** The four dead ones aren't noise: `E402` and `E501` mark
genuinely missing behaviour, while `E500`/`E502` are placeholders for the commercial mesh.

The error-response contract from `RFC §12.3` is implemented by `AIPError.to_dict()`:

```json
{"error_code":"AIP-E202","error_name":"MONETARY_LIMIT",
 "description":"Transaction amount exceeds per-transaction or per-day monetary limit",
 "detail":"..."}
```

Note that `verify_intent` never *raises* `AIPError` — it returns codes in
`VerificationResult.errors`. The exception class exists for callers who prefer to raise; the
only raiser in the SDK is `shield.AIPViolation`, a different exception type carrying the
whole result.

---

## 18. Layer 14 — Shield (enforcement DX)

`aip_protocol/shield.py`. The stated ambition, verbatim from the module docstring: *"This
module exists to make AIP adoption trivially easy. If your setup takes more than 2 lines, we
failed."* The mental model is helmet.js for agents.

### 18.1 The three entry points

```python
protect(func, *, actions, denied, limit, daily_limit, currency, domain,
        agent_name, geo, tier=TIER_1, on_violation="raise",
        passport=None, store=None) -> ProtectedAgent

shield(*, actions, denied, limit, ...) -> class decorator        (alias: shield_class)

protect_agent(agent_instance, *, actions, ...) -> same instance  (alias: shield_object)
```

All three converge on `ProtectedAgent`, whose `__call__` does, per invocation:

1. Build `parameters` from `kwargs`; positional args are stuffed into
   `params["_positional_args"]`.
2. `create_envelope(passport, action=self._action_name, target="self", parameters=params, tier=...)`
3. `sign_envelope(envelope, passport.private_key)`
4. `verify_intent(signed, passport.public_key, revocation_store=store)`
5. If invalid → `on_violation`: `"raise"` (default, throws `AIPViolation`), `"log"`
   (logger.warning + return `None`), `"silent"` (return `None`).
6. Otherwise call the wrapped function.

`functools.update_wrapper` preserves `__name__`/`__doc__`.

### 18.2 What this actually is, security-wise

**The passport signs the envelope and the same passport's public key verifies it.** There is
no second party. So Shield is not remote attestation — it is **local policy enforcement with
a cryptographic audit trail**: every call produces a signed, canonically-serialized,
nonce-bearing record of what was attempted and whether it was allowed, and the boundary /
revocation / replay engines are the real gate.

That is genuinely useful (a tamper-evident enforcement log plus a working kill switch), but
it is a different claim from "cryptographically verified by a counterparty". A compromised
process holds the private key and can bypass the wrapper entirely. The README's framing ("A
LangChain agent... AIP blocks unauthorized actions at the cryptographic layer") is true about
*boundary enforcement* and misleading about *cryptographic provenance* in the single-process
case.

### 18.3 Behavioural traps (all verified by execution)

| # | Trap | Observed |
|---|---|---|
| 1 | **`actions` names the allowlist, but the envelope's action is always `func.__name__`** | `protect(pay, actions=["send_money"])` → *every* call fails. Confirmed: `protect(actions mismatch): BLOCKED -> AIP blocked: AIP-E200` |
| 2 | **`@shield(actions=[...])` leaves unlisted methods completely unwrapped** | An unlisted method runs with **no** verification rather than being blocked. Confirmed: `unlisted method: ran unprotected`. Fail-open by omission |
| 3 | **`limit=0` = unlimited** | `protect(f, limit=0)` passes `amount=1e9`. Confirmed |
| 4 | **`shield`/`protect_agent` enumerate `dir(obj)` and `getattr` everything** | Properties are evaluated (side effects!), and every public callable becomes an "allowed action", including inherited methods |
| 5 | **`_check_kwargs` is dead code** | The deprecation/typo-help machinery (`_PROTECT_VALID_KWARGS`, `_DEPRECATED_KWARGS`, the friendly `TypeError`) is defined at lines 43-82 and **never called**. Confirmed by grep: one hit, the definition itself |
| 6 | **The README's Shield examples don't run** | README shows `@shield(passport, allowed_actions=[...], monetary_limit=100.0)`; the real signature is keyword-only with `actions=`/`limit=` and takes no positional passport. Confirmed: `TypeError: shield() got an unexpected keyword argument 'allowed_actions'`. Same for `@shield_class(passport)` and `shield_object(agent, passport)` |
| 7 | **A fresh passport per decorated object** | Each `@shield` class instance mints a *new* DID at `__init__`, so trust history and revocation targets differ per instance. Revoking "the agent" doesn't revoke tomorrow's instance |
| 8 | **Module-level `_default_store`** | Shared across everything shielded in the process |
| 9 | **Tier defaults to `TIER_1`**, bypassing risk-based auto-selection | Attestation runs; drift / delegation / trust do not |

Trap 6 is the one to fix first: the README is the primary onboarding surface and its central
"one-liner" examples raise `TypeError`. The `examples/` directory uses the correct modern API
throughout, so the fix is mechanical.

---

## 19. Layer 15 — Observe (observability DX)

`aip_protocol/observe.py`, added in v0.4.0 (commit `c33c6ab`). Positioned in its own
docstring as *"the free-tier growth engine"*: every `@observe` embeds a DID into the
customer's stack, and the upgrade to enforcement is a one-line diff.

### 19.1 Components

**`ObservationEvent`** (dataclass): `event_id` (16 hex), `agent_id`, `agent_name`, `action`,
`parameters{}`, `result`, `error`, `success`, `timestamp` (ISO), `latency_ms`, `caller`
(`file:line` of the call site, captured via `inspect.currentframe().f_back`).
`to_dict()` defensively `repr()`s non-JSON-serializable results.

**`ObservationStore`**: thread-safe `deque(maxlen=10_000)` ring buffer + per-agent counters
`{total, success, errors}` + a callback list. API: `record`, `on_event(cb)`, `events`,
`events_for_agent(id)`, `stats(agent_id=None)`, `clear()`, `export_json()`. Callbacks fire
**outside** the lock and exceptions in them are caught and logged — a misbehaving dashboard
hook can't deadlock or crash the agent.

**Module-global default store** with `get_observation_store()` / `set_observation_store()`.

**`passport(name, domain="localhost", **kwargs)`**: shorthand returning a real
`AgentPassport` (accepting `actions` / `denied` / `limit` / `daily_limit` / `currency`
through `kwargs`). This is the piece that makes the upgrade path work — the identity object
is identical to the one Shield consumes.

### 19.2 `ObservedCall.__call__`

Captures the caller frame → builds `parameters` (binding positional args to parameter names
via `inspect.signature`, skipping `self`, `repr()`-ing unserializable values) → starts the
timer → **executes the function unconditionally** → on success records `latency_ms` and
optionally the result; on exception records `error` and **re-raises**. `logger.debug` on both
paths.

Two invariants, both explicitly tested: **observe never blocks execution**, and **observe
never swallows errors**.

### 19.3 The three decorator forms

`observe` handles `@observe(agent)`, `@observe()` (auto-creates a passport named after the
function) and bare `@observe` (detected via `callable(agent) and not isinstance(agent, AgentPassport)`).
Applied to a class it wraps all public methods at `__init__` time (`_observe_class`);
`observe_agent(instance, ...)` does the same to a live object. Both stash `_aip_passport` and
`_aip_observe_store` on the target — the same attribute name Shield uses, which is what lets
you swap one for the other.

### 19.4 Privacy posture

- `log_params=True` by default — **arguments are captured**, so PII and secrets land in the
  store unless you pass `log_params=False`.
- `log_result=False` by default — return values are *not* captured. The asymmetry is
  deliberate and documented ("for privacy"), though arguably backwards: arguments are at
  least as sensitive as results.
- No redaction, no field allowlist, no sampling. In-memory only; nothing is transmitted.

### 19.5 Measured overhead

~**7.8 µs** per call over a trivial function (§25) — small enough to defend the "zero
overhead" claim at any realistic agent-call rate, though "zero" is marketing for "negligible".

---

## 20. Layer 16 — CLI

`aip_protocol/cli.py`, exposed as `aip` (click + rich).

### 20.1 Protocol commands

| Command | Purpose | Notes |
|---|---|---|
| `aip create-passport -d DOMAIN -n NAME -a ACTION... -m LIMIT -o DIR` | mint identity + keys | writes `passport.json` + both PEMs |
| `aip sign-intent -p DIR -a ACTION [-t TARGET] [--amount N] [--ttl S] [-o FILE]` | build + sign an envelope | prints JSON or writes a file |
| `aip verify -e ENVELOPE.json -k PUBLIC.pem` | run the pipeline | renders a rich table; **exit 0/1 on `result.passed`** — CI-friendly |
| `aip revoke AGENT_ID -r REASON` | kill switch | **writes to a per-process in-memory store — it does not persist.** Useful only as a demo |
| `aip inspect PATH` | pretty-print a passport dir or an envelope file | |

### 20.2 Scaffolding & cloud commands (added in `a557d62`)

| Command | Purpose |
|---|---|
| `aip init -n NAME --type agent\|swarm` | scaffolds `main.py` from an embedded template, plus `requirements.txt` and `.env.example`. The `agent` template uses `@shield(actions=[...], limit=...)`; the `swarm` template creates two shielded agents |
| `aip login [-t TOKEN] [-k API_KEY]` | saves `~/.aip/credentials.json` (**chmod 600** — good), or opens `{AIP_CLOUD_URL}/activate` and prompts for a pasted token |
| `aip status` | shows masked credentials and probes `{AIP_CLOUD_URL}/api/health` |
| `aip watch [-a AGENT_ID] [-n TAIL]` | pulls `{AIP_CLOUD_URL}/api/verifications`, renders a table, then **polls every 3 s** printing new rows |

`AIP_CLOUD_URL` defaults to `https://aip.synthexai.tech` and is env-overridable.

### 20.3 Issues

- `@click.version_option(version="0.2.0")` — **`aip --version` reports 0.2.0 while the
  package is 0.4.0.** Hardcoded rather than read from `__version__`.
- `aip watch` reuses the *same* `Request` object (built once, with the original `limit`
  query) inside the polling loop, and swallows all exceptions silently (`except Exception:
  pass`). A server error looks identical to "no new events".
- `aip revoke`'s in-memory-only behaviour isn't signposted in `--help`; a user could
  reasonably believe they revoked something durably.
- User-Agent strings are pinned to `aip-cli/0.2.0`.

---

## 21. The Conformance Suite

This is the most strategically interesting part of the repo: it is what converts "a library"
into "a candidate standard".

### 21.1 Structure

```
conformance/
├── vectors.json                 31 vectors + _meta (key material, canonical spec, reference bytes)
├── generate_vectors.py          deterministic generator — fixed seeds, fixed timestamps
├── run_conformance.py           reference runner (Python)
├── CANONICAL_SERIALIZATION.md   normative byte-level rules
└── README.md                    a porting guide for TS/Go/Rust/Java
```

### 21.2 Determinism

Everything derives from fixed seeds so any implementation can reproduce byte-identical
inputs:

| Key | Seed | Public key (hex) | Use |
|---|---|---|---|
| `agent_1` | `aa…aa` (32 B) | `e734ea6c2b6257de72355e472aa05a4c487e6b463c029ed306df2f01b5636b58` | primary signer |
| `agent_2` | `bb…bb` | `7d59c5623dd40a74aa4d5a32ac645d3b3f95daeae4c22be25476dd6a486f7382` | wrong-key tests |
| `hmac` | `cc…cc` | — | Tier 0 |

Fixed clock: `T_NOW = 2026-02-14T12:00:00+00:00`, `T_EXPIRED = 2024-01-01`. Nonces are a
monotonic counter formatted `nonce:{n:032x}` so they're exactly 38 chars.

Critically, the generator **signs using the SDK's own `_get_signable_payload`**, so vectors
and verifier cannot disagree about canonicalization by construction — and any *other*
implementation must match those bytes to pass.

### 21.3 The 31 vectors

| Cat | Count | Vectors |
|---|---|---|
| **A — envelope validity** | 5 | A01 valid · A02 expired (E101) · A03 bad version (E104) · A04 empty action (E103) · A05 short nonce (E105) |
| **B — signature** | 4 | B01 valid · B02 wrong key (E100) · B03 tampered payload (E100) · B04 HMAC Tier 0 valid |
| **C — replay** | 2 | C01 unique nonce · C02 duplicate nonce (E102, uses `verify_twice`) |
| **D — boundary** | 7 | D01 allowed · D02 not-allowed (E200) · D03 denied-wins (E201) · D04 amount == limit passes · D05 over limit (E202) · D06 geo match · D07 geo mismatch (E204) |
| **E — revocation** | 4 | E01 clean · E02 revoked (E400) · E03 **revoked at Tier 0** (E400) · E04 suspended (E401) |
| **F — tiered** | 2 | F01 Tier 0 skips attestation · F02 escalation permitted |
| **G — edge cases** | 2 | G01 zero amount passes · G02 negative amount passes |
| **H — serialization** | 5 | H01 float normalization · H02 decimal preserved · H03 recursive key order · H04 datetime `Z` · H05 nulls present |

Category H vectors carry a `canonical_payload_hex` field and the runner byte-compares,
reporting the **first differing byte offset** with surrounding context — a genuinely good
developer experience for someone porting the spec.

Four vector-level features let the JSON express dynamic scenarios: `verify_twice` (replay),
`revocations: [...]` (preload the store), `request_geo`, and `escalate_to`.

### 21.4 Verified result

```
AIP-1 Conformance Test Suite
Spec: AIP-1 | Vectors: 31 | Generated: 2026-02-14T12:00:00+00:00
  ✓ ALL 31 VECTORS PASSED (16.0ms)
```

**Documentation drift:** `conformance/README.md` still says "25 vectors across 7 categories"
in three places (headline, table, compliance badge). The suite is 31 across 8 — category H
and A05 were added by commit `ddff9ba` and the README wasn't updated.

**Portability caveat:** the runner prints box-drawing characters and dies with
`UnicodeEncodeError` on a Windows `cp1252` console. `PYTHONIOENCODING=utf-8` works around it;
the fix is `sys.stdout.reconfigure(encoding="utf-8")` or an ASCII fallback.

### 21.5 Why this mattered strategically

Commit `36af362` added a TypeScript SDK described as *"the second independent implementation
of AIP-1"*, passing all 31 vectors byte-identically. Two independent implementations agreeing
on a conformance suite is the classic bar for calling something a standard rather than a
library. That SDK was subsequently moved to the private repo (§28), so the public repo now
carries the suite but only one implementation.

---

## 22. The Test Suite

**98 tests total** (`tests/test_aip.py` 996 L, `tests/test_observe.py` 532 L).

### 22.1 Coverage map — `test_aip.py` (13 classes)

| Class | What it locks down |
|---|---|
| `TestCrypto` (9) | keygen, sign/verify, tamper detection, wrong key, PEM round-trip, b64 round-trip, HMAC + negative cases |
| `TestPassport` (3) | create, save/load round-trip, auto-naming |
| `TestEnvelope` (6) | creation, **all three auto-tier paths**, signing, JSON round-trip, hash determinism |
| `TestVerification` (10) | happy path + E100/E201/E200/E202/E101/E400/E401/E102/E302 |
| `TestTrustScore` (5) | zero for new agents, growth, violation decay, revocation penalty, threshold |
| `TestRevocationStore` (4) | revoke, suspend + expiry, reinstate, nonce replay |
| `TestIntegration` (3) | **full lifecycle** (create→sign→verify→revoke→verify-fails), persistence round-trip, monetary tier escalation |
| `TestTieredVerification` (5) | per-tier gating, Tier 0 still catches boundary violations, Tier 1 catches revocation |
| `TestIntentClassifier` (5) | exact/semantic match, cross-group drift, Tier 2 flagging, group table |
| `TestAttestation` (3) | model-hash and prompt-hash mismatch, correct hashes pass |
| `TestDelegation` (2) | valid chain, expired link |
| `TestGeoRestriction` (2) | allowed, blocked |
| `TestRevocationRehydration` (4) | rehydrate, skip expired suspensions, sync-time update, nonce cache bounded |
| `TestSchemaValidation` (1) | empty action |

### 22.2 Coverage map — `test_observe.py` (9 classes)

`TestObservationEvent` (4) · `TestObservationStore` (9, incl. ring-buffer eviction and
callback-error isolation) · `TestObserveFunction` (8) · `TestObserveClass` (3, incl. private
methods untouched) · `TestObserveAgent` (2) · `TestPassportShorthand` (4) · `TestGlobalStore`
(1) · **`TestUpgradePath` (2)** · `TestObserveIntegration` (1).

`TestUpgradePath` is the commercially load-bearing one: it asserts a passport created for
`@observe` works unchanged with `protect()`, and that the DID is stable across both.

### 22.3 Actual run

```
98 tests: 97 passed, 1 failed in 0.43s

FAILED tests/test_observe.py::TestObserveFunction::test_observe_tracks_latency
  assert store.events[0].latency_ms >= 10
  AssertionError: assert 8.95 >= 10
```

**This is a flaky timing assertion, not a logic defect.** The test does `time.sleep(0.01)` and
asserts the measured latency is `>= 10 ms`; on this Windows host `perf_counter` measured
8.95 ms. The observability code is correct; the threshold is not portable. Fix: assert `>= 5`,
or assert relative ordering instead of an absolute floor.

The README claims "98 tests, all passing" — accurate on the author's machine, not portable.

### 22.4 What isn't covered

No tests for: `shield.py` (the entire one-liner enforcement API — no test file exists),
`cli.py`, `per_day` limits (unenforced), boundary monotonicity (unenforced), staleness /
`AIP-E501`, principal revocation, `RevocationStore` under real thread contention, or
malformed/hostile JSON into `envelope_from_json`.

---

## 23. Examples & Demos

### 23.1 `examples/` — eight self-contained scripts, zero external deps

| File | Teaches |
|---|---|
| `01_quickstart.py` | `protect()` in three steps; `$50` passes, `$5000` raises `AIPViolation` |
| `02_protect_agent.py` | wrapping an existing instance; `actions` + `denied` + `limit` together |
| `03_shield_decorator.py` | `@shield` on a class, with `geo="US"` |
| `04_full_pipeline.py` | the manual protocol: passport → envelope → sign → verify → violation |
| `05_kill_switch.py` | revoke, then watch even a `$0` read get rejected |
| `07_multi_agent.py` | buyer/seller handshake; `first_contact=True` forces Tier 2 |
| `08_geo_restriction.py` | US / GB / RU with `request_geo` |
| `09_observe_agents.py` | all eight `@observe` features incl. callbacks, stats, export, and a live `@observe → protect()` upgrade proof |

(`06_langchain.py` is gitignored — it belonged to the private `aip-langchain` adapter.)

### 23.2 `attack_demo.py` — the demo reel

A theatrical, colour-coded, `slow_print`-animated walkthrough of five attacks against a
procurement agent (`$500/txn`, US-only, 3 allowed / 2 denied actions):

1. **Monetary violation** — `$15,000` payment → `AIP-E202`
2. **Unauthorized action** — `delete_data` (deny list) → `AIP-E200`/`E201`
3. **Replay** — resubmit a valid signed envelope → `AIP-E102`
4. **Geo violation** — request from `RU` → `AIP-E204`
5. **Kill switch** — revoke, then a *perfectly legitimate* `read_invoice` → `AIP-E400`

It narrates the trust score degrading across the sequence and prints a summary ("Money Lost:
$0.00"). Effective as a sales artifact. Minor nit: it defines `BLACK` *after* the functions
that reference it (works because Python resolves globals at call time).

### 23.3 `demos/langchain_protected_tools/` (346 L)

Builds an `AIPProtectedTool` wrapper (create → sign → verify → execute-or-return-error-string)
around four plain functions, one passport, per-tool boundaries:

| Tool | Status | Limit |
|---|---|---|
| `search_database` | allowed | — |
| `send_email` | allowed | — |
| `transfer_funds` | allowed | $500/txn |
| `delete_records` | **denied** | — |

Seven scenarios ending in kill switch → **reinstate**. No LLM key needed. The closing slide
advertises the (private) `aip_langchain` package's `@aip_tool(limit=500)` decorator.

### 23.4 `demos/crewai_financial_compliance/` (312 L)

Three agents with distinct passports — `AnalystAgent` (read-only; denies trade/transfer/
delete), `TradingAgent` ($10k limit), `AuditAgent` (read + report only) — across six
scenarios. The payoff is **selective revocation**: kill the trader, and the analyst and
auditor keep working. That is the multi-agent argument for per-agent identity in one
screenshot.

### 23.5 `demos/interactive/app.py` (578 L)

A FastAPI service on `:5050` with an embedded single-file dark-mode dashboard (Inter +
JetBrains Mono, CSS custom properties, no build step).

| Route | Behaviour |
|---|---|
| `GET /` | the HTML dashboard |
| `GET /api/agents` | the three pre-registered agents + live revoked/suspended status |
| `POST /api/verify` | full create→sign→verify; returns verdict, tier, errors, trust score, **`verification_time_us`**, and the complete signed envelope JSON |
| `POST /api/revoke` | kill switch |
| `POST /api/reinstate` | restore |

Requires `fastapi` + `uvicorn`, which are **not** declared in `pyproject.toml` (not even as an
extra). It binds `0.0.0.0` with no auth — fine for a laptop demo, never expose it.

---

## 24. The Documentation Site

`docs/index.html` — 957 lines, single file, GitHub Pages. Self-contained except Google Fonts.

Sections: hero ("The **HTTPS** for AI Agents" + `pip install aip-protocol` with a clipboard
button) → Problem (No Identity / No Boundaries / No Kill Switch) → Solution (six cards) →
8-step pipeline visual + three tier cards → Quick Start code → Frameworks → CTA.

Consistency notes: the site labels step 5 "Attestation — Ed25519 signature" (conflating two
different steps — attestation and signature are steps 6 and 4 in the code); its "Live Demo"
button points at `https://korven.cc` while every other surface uses `aip.synthexai.tech`; and
the framework demo links use `/tree/main/...` on a repo whose default branch is `master`, so
they 404.

---

## 25. Measured Performance

Benchmarked on this machine (Windows 11, CPython 3.10.11), median of 300 iterations:

| Operation | Median | Min | Max | README target |
|---|---|---|---|---|
| `verify_intent` Tier 0 (HMAC) | **0.041 ms** | 0.037 | 0.313 | <1 ms |
| `verify_intent` Tier 0 (Ed25519 fallback) | **0.121 ms** | 0.109 | 0.386 | <1 ms |
| `verify_intent` Tier 1 | **0.128 ms** | 0.113 | 0.308 | ~5 ms |
| `verify_intent` Tier 2 | **0.140 ms** | 0.116 | 1.401 | ~50–100 ms |
| `sign_envelope` | **0.066 ms** | — | — | — |

End-to-end wrapper overhead (2,000 iterations over a trivial function):

| Path | Per call | Delta over raw |
|---|---|---|
| raw Python call | 0.05 µs | — |
| `@observe` | **7.8 µs** | +7.8 µs |
| `protect()` (create + sign + verify) | **241 µs** | +241 µs |

**Reading these numbers.**

- The published tier targets are conservative by 10–700×. Real Tier 2 is ~0.14 ms, not
  50–100 ms. Understating performance is the safe direction, but it also undersells the
  product and suggests the numbers were estimated rather than measured.
- **The tiers barely differ in cost** (0.121 → 0.128 → 0.140 ms for Ed25519). The expensive
  operation is the Ed25519 verify plus canonical serialization, which *every* tier pays; the
  extra Tier 1/2 checks are dict lookups and a linked-list walk. **The only tier that buys
  real speed is Tier 0 *with* an HMAC key (3× faster).** This substantially undercuts the
  complexity argument for tiering in a purely local deployment — tiering earns its keep when
  Tier 2 implies a *network* call to a mesh, which is exactly the commercial product.
- `protect()`'s 241 µs is dominated by minting the envelope, signing, and Pydantic
  serialization — not by verification. At 1,000 agent actions/second that's ~24% of one core.
- `@observe` at 7.8 µs is genuinely negligible.

---

## 26. Spec ↔ Implementation Divergences

The repo carries three normative-ish documents (`RFC-001.md`, `RFC-001-manifesto.md`,
`conformance/CANONICAL_SERIALIZATION.md`) plus a README. They do not all agree with the code.

| # | Topic | RFC / docs say | Code does | Impact |
|---|---|---|---|---|
| 1 | `protocol_version` | MUST equal `"AIP-1"` (§6.2 step 1); every example shows it | `SUPPORTED_VERSIONS = {"1.0.0"}`; envelopes carry `"1.0.0"` | **Interop-breaking.** An implementation written from the RFC emits `"AIP-1"` and is rejected `AIP-E104` |
| 2 | Proof suite | `"Ed25519Signature2024"` throughout | `"Ed25519Signature2020"` | Cosmetic (never validated) but confusing |
| 3 | Attestation field | `model_hash` | `build_hash` | Canonical-payload mismatch across implementations |
| 4 | Attestation methods | `self_reported \| framework_registry \| third_party_audit` | `self_reported \| framework_registry \| tee_hardware` | Enum mismatch |
| 5 | Boundary monotonicity | MUST enforce (§4.5, §6.2 step 11) | Field written, never read | **Core security property unimplemented** |
| 6 | Per-day monetary limit | Defined in the cage (§4.3) and in the error text | Never enforced | Silent gap |
| 7 | `data_access` | Defined in the cage | Never enforced | Silent gap |
| 8 | Tier selection | Risk-relative (% of the agent's own limit) | Flat `amount > 100`, ignores boundaries | Wrong risk ordering (§9.1) |
| 9 | Tier 0 HMAC key exchange | X25519 agreement after a Tier 1 handshake, ephemeral keys (§7.2) | Caller passes `bytes` to both sides | Fine locally, undefined cross-org |
| 10 | Revocation staleness | SHOULD return `AIP-E501` (§8.4) | Returns `NOT_REVOKED` + `confidence="weak"`; E501 never raised | **Fail-open** (§15.4) |
| 11 | Principal revocation | `AIP-E402` | Reported as `AIP-E400`, and only via the stale-gated deep path | Code never emitted; behaviour unreliable |
| 12 | Nonce capacity | SHOULD support ≥1,000,000 | `MAX_NONCE_CACHE = 100_000`, arbitrary eviction | 10× under spec, non-deterministic eviction |
| 13 | Nonce retention | ≥ max envelope TTL, time-based | No time-based expiry at all | Unbounded retention below the cap |
| 14 | Clock skew | SHOULD allow ~5 s grace (§14.2) | Strict `now > expires_at` | Marginal false rejections |
| 15 | Private keys | MUST be encrypted at rest (§11.2) | `NoEncryption()` PEM, no chmod | Direct MUST violation |
| 16 | Key rotation | Full procedure specified (§11.3) | No implementation | Missing feature |
| 17 | `AIP-E105` | Absent from the RFC error table (§12.2) | Implemented and conformance-tested | RFC needs updating |
| 18 | Error count | README + manifesto: "22 codes" | 23 | Doc bug |
| 19 | Step numbering | RFC: 12 steps; README: 8; code comments: 8 with letters | — | Three inconsistent maps of one pipeline |
| 20 | Conformance size | `conformance/README.md`: "25 vectors, 7 categories" | 31 vectors, 8 categories | Doc bug |
| 21 | Shield API | README: `@shield(passport, allowed_actions=[...], monetary_limit=...)` | keyword-only `actions=`/`limit=`, no positional passport | **README examples raise `TypeError`** |
| 22 | Test count | "98 tests, all passing" | 98 tests, 1 timing-flaky off the author's machine | Minor |
| 23 | Trust model | "Bayesian" (README, manifesto, docs site) | Fixed-weight linear sum | Terminology |
| 24 | Revocation propagation | Manifesto: "zero propagation delay" | RFC §8.4 explicitly disclaims this; local store only | Manifesto oversells what the RFC retracts |
| 25 | CLI version | package 0.4.0 | `aip --version` → 0.2.0 | Doc bug |
| 26 | `runtime` string | — | hardcoded `"aip-sdk/0.1.0"` | Stale telemetry |

Items 1, 5, 10 and 21 change behaviour rather than prose.

---

## 27. Security Model & Threat Analysis

### 27.1 What AIP genuinely provides

| Property | Mechanism | Strength |
|---|---|---|
| **Message integrity** | Ed25519 over a canonical payload that includes the boundaries | Strong — 128-bit security; tampering with the cage invalidates the signature |
| **Non-repudiation of intent** | The agent signs *what it intends to do* before doing it | Strong, given key custody |
| **Replay resistance** | Per-verifier nonce cache | Good within one process; probabilistic above 100k nonces; not cross-process |
| **Boundary enforcement** | Deterministic predicates on a signed cage | Strong for allow/deny/per-txn/time; absent for per-day/data-scope |
| **Kill switch (agents)** | `is_revoked` at every tier, ahead of the tier exits | Strong locally; conformance vector `E03` locks in that Tier 0 cannot bypass it |
| **Kill switch (principals)** | Deep-check only, stale-gated | **Weak** (§15.4) |
| **Auditability** | 23 structured codes, `envelope_hash`, `VerificationResult.detail` | Strong |
| **Zero-network verification** | No I/O in the verify path | Real — verified by inspection |

### 27.2 The trust boundary question

The essential thing to be clear-eyed about: **in the single-process Shield deployment, the
signer and the verifier are the same entity holding the same key.** Cryptography there buys
*tamper-evidence and a canonical audit record*, not adversarial verification. An attacker
with code execution in that process can:

- read the private key from memory or `private.pem` (unencrypted on disk),
- call the underlying unwrapped function directly (`ProtectedAgent._func`),
- mint a new passport with a wider cage,
- or simply not use AIP.

Where AIP's cryptography becomes load-bearing is the **cross-party** case: agent A signs, and
a *different* organisation's verifier B checks against A's published public key and a shared
revocation registry. That is the architecture the RFC describes and the mesh product
implements. The public SDK supports it structurally (verifier-only passports, `did:web`
addressing, `registered_frameworks`) but ships no discovery or registry mechanism, so most
current usage is the single-process case.

**The honest framing:** AIP's in-process value is *a policy engine with a cryptographic audit
trail and a working kill switch* — real defence-in-depth against a *confused* agent
(hallucination, or prompt injection driving it to call a tool it shouldn't). It is not,
in-process, a defence against a *compromised runtime* — and `RFC §13.2` says exactly that.

### 27.3 Threat table

| Threat | Handled? | Notes |
|---|---|---|
| Prompt injection → out-of-scope tool call | ✅ | The primary use case. Boundary check rejects before execution |
| Hallucinated over-limit transaction | ✅ | `AIP-E202` |
| Envelope tampering in transit | ✅ | Signature covers everything but `proof` |
| Replay of a captured envelope | ✅ (bounded) | Per-process cache; §15.3 caveats |
| Compromised agent runtime / key theft | ❌ by design | RFC §13.2; mitigation is revocation *after* detection |
| Malicious sub-agent exceeding delegated scope | ❌ | Monotonicity unenforced (§14.2) |
| Revoked principal continuing to act | ⚠️ | Fails open after 500 ms (§15.4) |
| Nonce-burning DoS against a victim's envelope | ⚠️ | Replay check precedes signature check (§10.3) |
| Trust-score griefing | ⚠️ | Any submittable envelope can record a violation |
| Unknown-verb false positives at Tier 2 | ⚠️ | Classifier taxonomy is closed (§12.3) |
| Sybil / new-identity abuse | ⚠️ | Bounded by DNS control of `did:web` — but nothing in the SDK *verifies* DNS control |
| Post-quantum adversary | ❌ acknowledged | RFC §14.5; `proof.type` reserved for migration |
| Secrets leaking into observability | ⚠️ | `@observe(log_params=True)` by default, no redaction |

### 27.4 Deployment hardening checklist

1. Pin `tier=VerificationTier.TIER_2` for anything consequential — don't rely on
   auto-selection (§9.1).
2. Pass explicit `RevocationStore` / `TrustScoreEngine` instances per tenant; never share the
   module singletons in a multi-tenant server.
3. Call `store.touch_sync()` on a timer (or after every mesh poll) so principal revocation
   doesn't silently fail open.
4. Encrypt `private.pem` at rest or keep keys in an HSM/KMS — `AgentPassport.save()` will not
   do it for you, and won't restrict file permissions either.
5. Set `log_params=False` on `@observe` for anything touching PII.
6. Enumerate `actions` explicitly in `@shield` — and remember unlisted methods are
   *unprotected*, not blocked.
7. Supply `request_geo` if you declare `geo_restriction`; otherwise the boundary is inert.
8. Don't rely on `per_day` or `data_access` — they are declarations, not controls.

---

## 28. Open Source ↔ Commercial Boundary

The `.gitignore` header is explicit: `# ── Commercial Product (PRIVATE — never push) ──`.

**Excluded from the public repo:** `kya_api/`, `mesh/`, `dashboard/`, `integrations/`,
`sdks/`, `INTERNAL_README.md`, `aip_protocol/mesh.py`, `examples/06_langchain.py`, `*.pem`,
`Dockerfile`, `docker-compose.yml`, `Caddyfile`, `start.sh`, `setup.sh`, `data/`.

Commit `4e538e2` (*"chore: remove paid features from public repo"*) performed the carve-out,
deleting 3,624 lines: the mesh client, three framework integration packages (`aip-langchain`,
`aip-crewai`, `aip-autogen`) and the entire TypeScript SDK.

### 28.1 What the mesh client did (recoverable from git history)

`aip_protocol/mesh.py` (207 L) was a `MeshClient(api_key, mesh_url="https://mesh.synthexai.tech")`
that:

- opened a background daemon thread consuming **Server-Sent Events** from `/mesh/events`,
  with auto-reconnect and 5 s backoff,
- applied `revocation` / `suspension` events directly into a local `RevocationStore`,
- exposed `revoke()`, `suspend()`, `status()` over REST.

The design is exactly the "local cache + hot push" model that `revocation.py`'s docstring
describes — meaning the open-source store was purpose-built as the client half of a paid
service. Claimed propagation: `<50 ms`.

### 28.2 What the framework adapters looked like

`aip-langchain` exported `aip_tool`, `AIPTool`, `AIPToolkit` — a decorator form
`@aip_tool(limit=500)` wrapping a LangChain tool in create→sign→verify. `aip-crewai` and
`aip-autogen` were parallel packages. The public `demos/` reimplement these wrappers inline so
the demos still run without the private code.

### 28.3 The TypeScript SDK

Commit `36af362` — `types.ts`, `canonical.ts`, `crypto.ts` (`@noble/ed25519` v3),
`revocation.ts`, `verification.ts`, `conformance.ts`, `mesh.ts`. Passed all 31 vectors
byte-identically. Its removal is why the public repo's "any implementation can conform" story
now has a suite but no second implementation to demonstrate it.

### 28.4 The value split, as the README frames it

| Local (free, this repo) | Cloud (paid) |
|---|---|
| Signing, verification, boundaries, tiers | **Revocation mesh** — kill across N deployments |
| Local revocation store | **Persistent trust scores** — survive restarts |
| Per-process nonce cache | **Cross-org replay detection** — shared nonce registry |
| `VerificationResult` in memory | **Compliance audit log** — immutable, SOC2/HIPAA |
| `did:web` strings | **Agent identity registry** — DNS-for-agents |
| Demo-grade wrappers | **Managed framework adapters** |
| — | **Dashboard** — monitoring, kill switch, debugger |

The argument is coherent: every paid feature is one that is *intrinsically* multi-process or
multi-org, which a local library genuinely cannot provide. The free tier's job is
distribution — `@observe` plants a DID in the customer's stack at zero risk, and `@shield` is
one line away.

---

## 29. Evolution (git history)

22 commits, reading bottom-up as a coherent product narrative:

| Commit | Milestone |
|---|---|
| `665abd4` | v0.1.0 — the SDK exists |
| `3e694ac`…`024c4b8` | hosted API, design-partner CTA (three near-duplicate doc commits) |
| `b7c2801` | **"complete SDK engine rewrite — CTO audit v1"** — the current architecture |
| `a9831fe` | URL consolidation → `aip.synthexai.tech` |
| `77663ee` | professional README: spec, error taxonomy, architecture diagram |
| `4ed452e` | **security**: disable Swagger, **fix kill switch on Tier 0**, randomize seed password |
| `a5ec336` | RFC-001 public draft |
| `db20d2c` | attack demo — 5 scenarios |
| `2a0bb04` | RFC-001 rewritten IETF-style |
| `edded66` | **ecosystem**: one-liner API + 3 framework integrations + 8 examples |
| `3dc2899` | **conformance suite** — 25 vectors, 7 categories |
| `ddff9ba` | **interop**: float normalization, nonce validation, canonical spec → 31 vectors |
| `36af362` | **TypeScript SDK** — "second independent implementation", 31/31 |
| `8f4d079` | mesh client (Python + TS) — connects to the paid mesh |
| `4e538e2` | **carve-out**: paid features removed from the public repo |
| `a557d62` | DX: smarter shield, better errors, `init`/`login`/`watch`/`status` |
| `28a7b91` | v0.3.0 |
| `3f087f8` | GitHub Pages site |
| `ed7e53d` | framework demos + README/RFC refresh |
| `c33c6ab` | **v0.4.0 — `@observe`** (520 L module, 532 L tests, 283 L example) |

The arc is legible: *prototype → hardening audit → spec → proof (conformance) → second
implementation → commercialisation → developer experience → free-tier growth engine*.
`4ed452e` is notable — "fix kill switch on tier 0" is precisely the bug that conformance
vector `E03` now permanently guards against.

---

## 30. Findings & Recommendations

Ordered by severity. Every item was verified against the running code.

### P0 — behavioural / security

| # | Finding | Evidence | Fix |
|---|---|---|---|
| 1 | **Principal revocation fails open after 500 ms.** `_check_revocation` returns `NOT_REVOKED` when the store is stale, and principal revocation exists *only* in that path | Experiment B in §15.4: revoked principal + 0.7 s wait → `valid: True` | Move the principal check next to the agent check at step 5b (not staleness-gated), and emit `AIP-E501` (or fail closed) when data is stale |
| 2 | **Boundary monotonicity is unenforced** despite being a MUST in the RFC and defaulting to `True` on every link | grep: 2 references in the package, both writes | Implement the subset check in `_check_delegation`, or drop the field and the claim |
| 3 | **`@shield(actions=[...])` leaves unlisted methods unprotected** rather than blocked | `unlisted method: ran unprotected` | Wrap *all* public methods and use `actions` purely as the passport allowlist, so unlisted ones fail `AIP-E200` |
| 4 | **`AIP-E501` never emitted; `confidence="weak"` never consulted** | grep: 0 emission sites | Wire the staleness signal into the verdict |
| 5 | **Private keys written unencrypted, no file mode** | `crypto.py:58` `NoEncryption()`; `passport.save()` has no `chmod` | Add an optional passphrase and `chmod 0600` — the CLI already does this for credentials |

### P1 — correctness / semantics

| # | Finding | Fix |
|---|---|---|
| 6 | **Tier auto-selection ignores the agent's own limits** (flat `amount > 100`) | Implement the RFC's percentage-of-limit rule; make the sensitive-action set configurable |
| 7 | **Intent drift is effectively unreachable** — step 5 already rejects everything the classifier would reject | Either run drift independently of the allowlist (as a semantic check *on* allowlisted actions), or remove it and stop advertising it |
| 8 | **`per_day` and `data_access` are declared but unenforced** | Implement, or mark clearly as reserved in the models and docs |
| 9 | **Replay check precedes signature check**, enabling nonce burning | Move `check_nonce` after `SIGNATURE_CHECK` (keeping expiry first) |
| 10 | **Nonce eviction is arbitrary (`set.pop`)** with no time-based expiry | Use an `OrderedDict`/deque keyed by insertion time; evict by age first, then by pressure |
| 11 | **`AIP-E402` never emitted** — principal revocation reports `E400` | Return `PRINCIPAL_REVOKED` when the match is on `principal.id` |
| 12 | **`_check_kwargs` is dead code** — the friendly deprecation/typo errors never fire | Call it at the top of `protect`/`shield`/`protect_agent`, or delete it |
| 13 | **`protect(func, actions=[...])` blocks everything when `actions[0] != func.__name__`** | Use `actions[0]` (or an explicit `action=` kwarg) as the envelope action, or document loudly |
| 14 | **Module-level singletons** shared across tenants | Document; consider requiring explicit stores in a `strict` mode |
| 15 | **No clock-skew grace on expiry** | Add the RFC's 5 s tolerance |
| 16 | `_normalize_floats` raises on `NaN`/`±inf` | Reject non-finite floats at the schema layer |

### P2 — documentation (high user impact, low effort)

| # | Finding | Fix |
|---|---|---|
| 17 | **README Shield examples raise `TypeError`** — wrong API shape in the most-read section | Rewrite with `actions=`/`limit=` (the `examples/` dir is already correct) |
| 18 | RFC says `protocol_version: "AIP-1"`, code requires `"1.0.0"` | Pick one; if the RFC is authoritative, accept both for a deprecation window |
| 19 | "22 error codes" → 23 | Fix README + manifesto |
| 20 | `conformance/README.md` says 25 vectors / 7 categories → 31 / 8 | Update, including the badge text |
| 21 | Latency claims are 10–700× conservative | Publish measured numbers; they're better |
| 22 | "Bayesian trust score" is a weighted linear sum | Rename to "behavioural trust score" |
| 23 | Manifesto's "zero propagation delay" contradicts RFC §8.4 | Align the manifesto with the RFC |
| 24 | `aip --version` → 0.2.0; `runtime` → `aip-sdk/0.1.0`; User-Agent → `aip-cli/0.2.0` | Read from `__version__` |
| 25 | RFC error table omits `AIP-E105` | Add it |
| 26 | RFC `model_hash` vs code `build_hash`; `third_party_audit` vs `tee_hardware`; `Ed25519Signature2024` vs `2020` | Reconcile |
| 27 | docs site: "Live Demo" → `korven.cc`; framework links use `/tree/main/` on a `master`-default repo | Fix links |

### P3 — engineering hygiene

| # | Finding | Fix |
|---|---|---|
| 28 | **No tests for `shield.py` or `cli.py`** — the two most user-facing modules | Add `tests/test_shield.py` covering all three entry points and the traps in §18.3 |
| 29 | Flaky latency assertion (`>= 10 ms` after `sleep(0.01)`) | Assert `>= 5`, or compare relative ordering |
| 30 | Conformance runner crashes on Windows `cp1252` | `sys.stdout.reconfigure(encoding="utf-8")` + ASCII fallback |
| 31 | `demos/interactive` needs `fastapi`/`uvicorn`, undeclared anywhere | Add a `demo` extra in `pyproject.toml` |
| 32 | `crypto.py` imports `hashlib`/`hmac` mid-file | Move to the top |
| 33 | `verify_signature` catches bare `Exception` | Narrow it |
| 34 | `attack_demo.py` defines `BLACK` after its first textual use | Move the constant up |
| 35 | No CI config in the repo | Add a workflow running `pytest` + conformance on 3.10–3.13 × {linux, windows} |
| 36 | `aip watch` swallows every exception in its poll loop | Surface errors after N consecutive failures |

---

## 31. Glossary & Quick Reference

### 31.1 Glossary

| Term | Meaning |
|---|---|
| **AIP-1** | The protocol specification (`RFC-001.md`) |
| **`aip-protocol`** | The reference Python SDK (this repo) |
| **Agent** | Autonomous software acting for a principal; owns an Ed25519 key |
| **Principal** | The human/org ultimately accountable; delegates authority |
| **Agent Passport** | Identity + keys + boundary cage + attestation |
| **DID** | `did:web:<domain>:agents:<name>` — W3C decentralized identifier |
| **Intent Envelope** | The signed pre-execution declaration; the atomic protocol unit |
| **Boundary Cage** | allowed/denied actions, monetary limits, geo, time window, data scopes |
| **Verification Pipeline** | The ordered, tier-gated checks in `verify_intent` |
| **Tier 0/1/2** | Fast (HMAC) / standard (Ed25519 + attestation) / full (+ drift, delegation, trust) |
| **Canonical serialization** | The exact bytes that get signed (§7) |
| **Entropy / nonce** | `nonce:<32 hex>`, ≥38 chars, single-use per verifier |
| **Revocation vs Suspension** | Permanent (`suspended_until is None`) vs temporary |
| **Trust Score** | `[0,1]` behavioural score, local to each verifier |
| **Intent Drift** | Action semantically outside the declared scope (`AIP-E303`) |
| **Shield** | The enforcement decorator family |
| **Observe** | The zero-enforcement logging decorator family |
| **Revocation Mesh** | The commercial distributed kill switch |

### 31.2 Minimum working example

```python
from aip_protocol import (AgentPassport, create_envelope, sign_envelope,
                          verify_intent, RevocationStore, VerificationTier)

passport = AgentPassport.create(
    domain="yourco.com", agent_name="procurement-bot",
    allowed_actions=["read_invoice", "transfer_funds"],
    denied_actions=["delete_data"],
    monetary_limit_per_txn=50.0,
)

env    = create_envelope(passport, action="transfer_funds",
                         target="did:web:vendor.com",
                         parameters={"amount": 45.00, "currency": "USD"},
                         tier=VerificationTier.TIER_2)   # pin it — don't trust auto-select
signed = sign_envelope(env, passport.private_key)

store  = RevocationStore()
result = verify_intent(signed, passport.public_key,
                       revocation_store=store, request_geo="US")

if result.passed:
    ...  # execute
else:
    for e in result.errors:
        print(e.value, e.name, result.detail)
```

### 31.3 Command reference

```bash
# SDK
pip install aip-protocol
pip install -e ".[dev]"

# Tests + conformance
pytest tests/ -v
python conformance/run_conformance.py -v          # prefix PYTHONIOENCODING=utf-8 on Windows
python conformance/run_conformance.py -c boundary # one category
python conformance/run_conformance.py B03         # one vector
python conformance/generate_vectors.py            # regenerate after serializer changes

# Demos
python attack_demo.py
python examples/09_observe_agents.py
python demos/langchain_protected_tools/langchain_demo.py
python demos/crewai_financial_compliance/crewai_demo.py
python demos/interactive/app.py                   # needs fastapi + uvicorn → :5050

# CLI
aip create-passport -d yourco.com -n my-agent -a read_data -a transfer_funds -m 100
aip sign-intent -p ./agent_passport -a transfer_funds --amount 45 -o intent.json
aip verify -e intent.json -k ./agent_passport/public.pem
aip revoke "did:web:yourco.com:agents:my-agent" -r compromised
aip inspect ./agent_passport
aip init -n my-project --type agent
aip login | aip status | aip watch
```

### 31.4 One-page cheat sheet

| Question | Answer |
|---|---|
| What gets signed? | Everything except `proof`, canonicalized per §7 |
| What runs at every tier? | version, schema, expiry, nonce format, replay, signature, boundaries, **revocation** |
| What only runs at Tier 1+? | attestation, deep revocation |
| What only runs at Tier 2? | intent drift, delegation, trust threshold |
| Empty `allowed_actions` means? | Everything allowed |
| `limit=0` means? | Unlimited |
| Which parameter is checked for money? | `parameters["amount"]` only |
| Is geo checked without `request_geo`? | No |
| Does a revoked agent bypass via Tier 0? | No — conformance vector `E03` |
| Does a revoked *principal* always get caught? | **No** — see §15.4 |
| Does `@observe` ever block? | Never; it also never swallows exceptions |
| Same DID across observe and shield? | Yes, if you pass the same passport |
| Is anything sent over the network during verification? | No |

---

*Document generated from a full read of the repository at commit `c33c6ab` (v0.4.0).
All test runs, conformance runs, benchmarks and behavioural probes cited above were executed
against this working tree.*
