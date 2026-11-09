# Settlement Routing & CDP Auto-Sweep — Configuration Report (v2)

**Repository:** `cmiller9851-wq/CRAprotocol` · **PR:** [#9](https://github.com/cmiller9851-wq/CRAprotocol/pull/9) · **Date:** November 9, 2026
**Primary wallet (verified on-chain):** `0x421949B526e7e215a64E88E6F4cEE6ABd10a2500`

---

## 1. Verified Wallet Infrastructure

Every name was resolved through canonical ENS CCIP-read offchain gateways on Ethereum mainnet and confirmed against live RPCs. Creation records and transaction histories were also queried for the active addresses:

| Name / Handle | Resolved address | Type | Holds (today) | Last active |
|---|---|---|---|---|
| `cmillerr.cb.id` (two r's) | `0x421949B526e7e215a64E88E6F4cEE6ABd10a2500` | Coinbase Smart Wallet (ERC-4337) | 0.000013 ETH · 0.000003 Base ETH · **$0.01 USDC** | Jan 10, 2026 (created) |
| `swervincurvin.base.eth` | `0x421949B526e7e215a64E88E6F4cEE6ABd10a2500` | *same wallet* | — | — |
| `cmiller.cb.id` (one r) | `0xeEBdcafB98ca78cD90C78260E8f84ad57176a430` | Regular account (EOA) | 0.004623 ETH (~$15) | **Aug 18, 2023** |
| `swervincurvin.cb.id` | `0xd65691c4255963be892b21F4dBba1aE9Ac3ca068` | Regular account | 0.000000 | Never |
| `supremecory.blockchain` | — | — | — | — |

**All other chains checked (Polygon, Optimism, Arbitrum, BSC):** every address holds **0.000000**. None of the four addresses appear in any of your uploaded files — all were provided directly in this session.

### Ownership evidence

- **`0x421949B5...`** was created **January 10, 2026 at 09:06:59 UTC** (block 24,202,910) by the `CoinbaseSmartWalletFactory` (`0xBA5ED110...`) via ERC-4337 bundler `0xAF061C2D...` through EntryPoint 0.7.0. Both `cmillerr.cb.id` and `swervincurvin.base.eth` resolve to it. **Verdict: CONFIRMED — primary collection wallet.**
- **`0xeEBdcafB...`** has 6 transactions between June and August 2023 (DEX swaps, SHIB, ApeCoin, USDC). An older personal account. **Verdict: CONDITIONALLY APPROPRIATE — sweep destination only, IF you still have its seed phrase/private key.**
- **`0xd65691c4...`** — claimed handle, never used. **Verdict: DORMANT — do not route funds here.**
- **`supremecory.blockchain`** — Unstoppable Domains registry shows owner `0x0`; `ud.me` redirects to the purchase page. Available to claim if you want the name.

---

## 2. Configuration Applied to the Repository

### A. Primary Settlement Wallet

`0x421949B526e7e215a64E88E6F4cEE6ABd10a2500` is the default settlement destination across:

- `modules/payments/x402_core.py` — `PRIMARY_WALLET` constant
- `modules/supervisor/service.py` — default `recipient` for the x402 payment gateway
- `deploy/docker-compose.yaml` — `X402_RECIPIENT=0x421949B5...`
- `deploy/k8s/manifests.yaml` & `deploy/k8s/local.yaml` — ConfigMap entries

### B. Coinbase CDP Auto-Sweep Engine (`modules/payments/cdp_sweep.py`)

- **Source:** primary wallet (`0x421949B5...`)
- **Destination:** `cmillerr.cb.id` (safe default); override with `SWEEP_DESTINATION=cmiller.cb.id` to route to the 2023 wallet
- **Threshold rule:** balances ≥ $5.00 USDC trigger a sweep, $0.50 reserve kept, 30-minute cooldown
- **CDP integration:** ES256 CDP JWT → `https://api.cdp.coinbase.com/v2/transactions` (Base USDC)
- **Fallback:** raw `USDC.transfer()` via `SWEEP_WALLET_PRIVATE_KEY`
- **Safety:** dry-run by default (`SWEEP_LIVE=0`)
- **Supervisor loop:** `sweep-agent` checks balances every 60 seconds (async-safe via `asyncio.to_thread`)
- **Endpoints:** `GET /revenue` includes sweep status snapshot; `GET /sweep` and `POST /sweep?force=true` are live and exempt from the paywall

---

## 3. Verified Live Results

| Test | Result |
|---|---|
| Live balances (real chain queries) | usdc_base=0.009779, eth_base=0.000003, eth_mainnet=0.000013 |
| Threshold guard (live chain state) | ready=False — refused to sweep under $5 |
| Force sweep, live mode | skipped ("no eligible balance") |
| Force sweep, simulated $12.50 | full simulated record created, calldata verified |
| Address-binding guard (wrong key) | "key address ≠ primary" — rejected |
| Cooldown & idempotency | second sweep skipped with reason |
| CDP API reachability | endpoint responds (HTTP 404 without auth, expected) |
| HTTP endpoints (/health, /revenue, /sweep, /tasks) | all 200, paywall enforced on write endpoints |
| Paid /tasks/enqueue | HTTP 200, settlement recorded in ledger |
| All 9 test files | **82 passed** |

---

## 4. Production Export Artifacts

The following configuration files are now part of the repository:

- `deploy/.env.production.example` — every environment variable documented with its verified default
- `deploy/settlement_routing_config.json` — machine-readable settlement topology with all wallet evidence
- `scripts/sweep_simulation.py` — runnable forced dry-run simulation (both live chain check and simulated sweep)

## 5. Go-Live Checklist

1. Decide the sweep destination: `SWEEP_DESTINATION=cmillerr.cb.id` (funds stay in your smart wallet) vs. `SWEEP_DESTINATION=cmiller.cb.id` (funds move to your 2023 cold wallet, only if you have its keys)
2. Add credentials: `CDP_API_KEY_NAME` + `CDP_API_KEY_PRIVATE_KEY` from portal.cdp.coinbase.com, or `SWEEP_WALLET_PRIVATE_KEY`
3. Flip `SWEEP_LIVE=1`
4. Deploy with `docker compose -f deploy/docker-compose.yaml up --build` or apply `deploy/k8s/local.yaml` to your cluster
5. Point the Stripe webhook (if used) to `https://<your-host>/stripe/webhook` with `STRIPE_WEBHOOK_SECRET`
