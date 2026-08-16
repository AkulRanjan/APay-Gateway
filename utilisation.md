# Using Custos Effectively

Custos is most useful as a mandatory policy checkpoint before an agent borrows against, trades, or redeems a tokenized asset. It verifies market plausibility and claim freshness before a downstream protocol receives the request.

> Custos checks a simulated asset claim against a live Treasury market reference. It does not audit an issuer's private NAV, holdings, or legal redemption rights.

## 1. Start the gateway

Install the dependencies once, then start the API:

```powershell
python -m pip install -r requirements.txt
.\demo\start_live_demo.ps1
```

Use the interactive presenter view at `http://127.0.0.1:8000/demo`, API documentation at `http://127.0.0.1:8000/docs`, and the health endpoint at `http://127.0.0.1:8000/v1/health`.

For a repeatable offline presentation, use:

```powershell
python demo/run_local_demo.py
```

## 2. Recommended transaction flow

1. The agent creates an intent with a short expiry (normally five minutes or less).
2. The agent sends it to `POST /v1/intent` before contacting a lender, DEX, or execution service.
3. Custos validates the envelope, resolves the claim, fetches the market observation, and evaluates staleness, drift, and backing.
4. On `ALLOW`, either send the returned signed attestation to the downstream system or let Custos proxy to the optional `downstream` URL.
5. On `BLOCK`, stop the transaction. Branch on the `CUSTOS-Exxx` code; never treat a block as a warning.
6. Store every signed ALLOW with the transaction record and verify it when needed.

This puts the policy decision at one boundary instead of requiring each agent or protocol to reimplement the risk checks.

## 3. Send an intent

Example: an autonomous treasury agent requests a loan against a 3-month Treasury token.

```powershell
$now = [DateTime]::UtcNow
$intent = @{
  envelope_version = "custos/1"
  agent_id         = "did:web:acme.com:agents:treasury-bot"
  action           = "borrow_against"
  asset_id         = "TKN-UST-3M-001"
  amount           = 50000.00
  currency         = "USD"
  issued_at        = $now.ToString("o")
  expires_at       = $now.AddMinutes(5).ToString("o")
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/v1/intent" `
  -ContentType "application/json" `
  -Body $intent
```

An ALLOW returns the asset, agent, action, computed scores, live-market reference, expiry, Ed25519 signature, and public key. The attestation is time-limited; do not reuse it after `expires_at`.

## 4. Verify an ALLOW independently

Save the returned ALLOW JSON as `attestation.json`, then verify it outside the gateway process:

```powershell
python demo/verify_attestation.py attestation.json
```

The verifier rebuilds the canonical JSON payload, excludes `signature` and `public_key`, and validates the embedded Ed25519 signature. A lender, auditor, or another agent can run the same verification without trusting the gateway process.

## 5. Forward only allowed transactions

Add a `downstream` URL to the intent when Custos should forward an approved request itself:

```json
{
  "envelope_version": "custos/1",
  "agent_id": "did:web:acme.com:agents:treasury-bot",
  "action": "borrow_against",
  "asset_id": "TKN-UST-3M-001",
  "amount": 50000.00,
  "currency": "USD",
  "issued_at": "2026-08-16T10:00:00Z",
  "expires_at": "2026-08-16T10:05:00Z",
  "downstream": "https://lender.example/loan"
}
```

For an ALLOW, Custos forwards the intent and attaches a base64-encoded signed attestation in the `X-Custos-Attestation` header. For a BLOCK, it never calls the downstream service. A downstream connection failure is `CUSTOS-E400`.

Only configure controlled, allow-listed downstream URLs in a production deployment. Accepting arbitrary user-provided URLs is appropriate for this local demo but would create an SSRF risk in a deployed gateway.

## 6. Act on responses

| Result | Agent or protocol action |
|---|---|
| `ALLOW` | Verify/store the attestation, then continue with the transaction. |
| `CUSTOS-E100`, `E102`, `E103` | Correct the malformed, expired, or future-dated intent and submit a new one. |
| `CUSTOS-E200` | Reject or onboard the asset into a trusted claim registry. |
| `CUSTOS-E101` | Require a newer claim attestation before retrying. |
| `CUSTOS-E201` | Pause collateral acceptance or request updated issuer data; do not simply widen the threshold. |
| `CUSTOS-E202` | Reduce exposure, require additional collateral, or block the asset. |
| `CUSTOS-E203` | Map the asset tenor to a supported Treasury curve field. |
| `CUSTOS-E300`, `E301` | Retry later or use an approved independent oracle; retain fail-closed behavior. |
| `CUSTOS-E400` | Keep the successful attestation but retry the downstream call within its validity period. |

## 7. Diverse use cases

### A. Agentic lending collateral gate

**Situation:** A lending protocol lets an autonomous borrower pledge tokenized Treasury units.

**Use Custos:** The borrower submits `borrow_against` through Custos. The lender accepts only requests carrying a valid signed ALLOW.

**Value:** The lender does not extend liquidity against a stale claim or one whose stated yield is no longer plausible against the Treasury curve.

```text
Agent → Custos → signed ALLOW → lending protocol → loan execution
                 BLOCK       → no loan execution
```

### B. DEX trade pre-flight check

**Situation:** A market-making agent is about to sell a large position in a tokenized Treasury asset.

**Use Custos:** Send a `trade` intent before placing the order. If the asset's yield is materially inconsistent with the live reference, block the trade and route it to human review.

**Value:** Stops automated liquidity from pricing an asset as if an outdated yield claim were still current.

### C. Redemption triage

**Situation:** A redemption agent processes large redemptions from several tokenized funds.

**Use Custos:** Submit a `redeem` intent for each asset. A stale claim produces `CUSTOS-E101`, so the agent can hold that request and process only assets with current evidence.

**Value:** Reduces operational exposure while ensuring that healthy redemptions are not delayed by unrelated assets.

### D. Treasury-management policy for a DAO

**Situation:** A DAO treasury bot reallocates stablecoin reserves into tokenized Treasury instruments.

**Use Custos:** Make an ALLOW a required condition in the governance execution policy. Store each signed attestation with the proposal execution record.

**Value:** Provides an auditable, reproducible reason why a bot did or did not move treasury capital.

### E. Multi-agent risk coordinator

**Situation:** Several specialist agents—trading, lending, and settlement—share the same asset universe.

**Use Custos:** Put one gateway in front of all of them and use the error code as a common state signal. For example, an `E201` from the lending agent can automatically pause the trading agent's strategy for that same asset.

**Value:** One consistent policy, rather than multiple agents making contradictory decisions from different market snapshots.

### F. Compliance and audit evidence

**Situation:** A regulated operator needs evidence that automated capital movement passed a defined risk control at the time of execution.

**Use Custos:** Archive the original intent, signed ALLOW, public key, verification result, and downstream transaction reference together.

**Value:** The signature proves the decision payload has not changed after it was issued; the scores and reference fields explain the decision.

## 8. Operating guidance

- Keep the default **fail-closed** behavior. An unavailable oracle should block, not approve.
- Use a persistent PEM key through `CUSTOS_PRIVATE_KEY` outside demos. Publish and rotate its public key through your normal key-distribution process.
- Treat thresholds as policy: calibrate `CUSTOS_DRIFT_THRESHOLD`, staleness limits, and backing floors for the asset class and risk appetite.
- Monitor `GET /v1/health`, `CUSTOS-E300`, and `CUSTOS-E301`. Repeated oracle failures are an operational issue, not a reason to bypass the control.
- Keep attestation TTLs short and bind the downstream system to verification of the signature, asset, action, amount, and expiration.
- Replace the seeded registry with authenticated on-chain or issuer claim sources before using Custos for real capital.

## 9. Demo presentation sequence

1. Open `/demo` and click **Sync live market**.
2. Show the current Treasury observation.
3. Run the stale asset: explain `CUSTOS-E101`.
4. Run the recent-but-drifted asset: explain `CUSTOS-E201` and why freshness alone is insufficient.
5. Run the healthy asset: show the signed ALLOW.
6. Verify the saved attestation with `demo/verify_attestation.py`.

This sequence demonstrates both safety (blocks) and utility (a verified transaction can proceed).
