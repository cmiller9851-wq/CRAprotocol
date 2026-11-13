# GitHub dual-rail coordination

The `Non-blocking settlement coordinator` workflow provides one GitHub Actions control plane for observing the Stripe rail and a wallet rail independently.

## What it does

- Runs on demand or every six hours.
- Reads a sanitized Stripe snapshot using `STRIPE_API_KEY` and optional `STRIPE_ACCOUNT_ID`.
- Reads a wallet native balance through a configured JSON-RPC endpoint using `WALLET_RPC_URL`, `WALLET_ADDRESS`, and optional `WALLET_CHAIN`.
- Uploads short-retention sanitized artifacts and writes a GitHub Actions summary.
- Records unavailable credentials, provider errors, and unresolved wallet configuration as evidence gaps.

## What it never does

The workflow never rejects, pauses, cancels, retries, holds, or reroutes an incoming payment. It never creates a PaymentIntent, Checkout Session, invoice, payout, or transfer. It never signs or broadcasts a wallet transaction and never reads a private key.

A provider being unavailable cannot block the provider's own payment rail. The two observations are independent and the jobs use `continue-on-error` so one rail cannot stop the other.

## Configuration

Store only the following non-source values in GitHub Actions secrets/variables:

- `STRIPE_API_KEY` — read-only or appropriately scoped Stripe API credential.
- `STRIPE_ACCOUNT_ID` — optional account identifier for evidence labeling.
- `WALLET_RPC_URL` — read-only JSON-RPC endpoint.
- `WALLET_ADDRESS` — verified public wallet address to observe.
- `WALLET_CHAIN` — optional display label such as `base`, `ethereum`, or `polygon`.

Never add private keys, seed phrases, webhook secrets, or unrestricted transfer credentials to this workflow.

## Live routing boundary

If live routing is later required, it must be a separate reviewed workflow with explicit amount, currency/asset, network, destination, idempotency key, approval environment, and reconciliation evidence. This observer is intentionally not a payment executor.
