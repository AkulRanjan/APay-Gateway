# Custos implementation contract

Custos is a fail-closed gateway for asset-truth attestations. Keep dependencies one-way: `gateway` may use `attest`, `claims`, and `oracle`; `attest` may use models/config only; `claims` and `oracle` do not import gateway.

## Fixed data contracts

- `Intent`: `envelope_version="custos/1"`, non-empty `agent_id`, action of `borrow_against|trade|redeem`, positive USD amount, UTC `issued_at` and `expires_at`, optional downstream URL.
- `Claim`: asset identifier, Treasury tenor, claimed NAV/backing/tokens/yield, and last-attested timestamp.
- `Observation`: source, tenor, observed yield in integer bps, record date, fetch time, cache flag.
- ALLOW responses are signed Ed25519 attestations; BLOCK responses use the `CUSTOS-Exxx` taxonomy.

## Evaluation contract

`evaluate(intent: Intent, claim: Claim | None, obs: Observation | None) -> Scores | BlockResponse`

It must evaluate in this order: unknown asset E200; unavailable oracle E300; stale observation E301; stale claim E101; yield drift E201; backing ratio E202. The gateway performs envelope E100/E102/E103 checks beforehand. Never fail open.

## Error codes

`E100` malformed envelope; `E101` claim stale; `E102` intent expired; `E103` clock skew; `E200` unknown asset; `E201` yield drift; `E202` insufficient backing; `E203` unsupported tenor; `E300` oracle unavailable; `E301` stale oracle data; `E400` downstream unavailable.

## Signing contract

Canonicalize the JSON object excluding `signature` and `public_key`, with sorted keys, compact separators, ASCII encoding. Sign the resulting UTF-8 bytes with Ed25519. Keep `demo/verify_attestation.py` independent of application modules.
