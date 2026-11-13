# Normal settlement intake

The normal settlement flow accepts payment through independent collection rails and reconciles the result afterward. It does not use a webhook as the payment rail and does not require sender pre-authorization.

## Stripe collection

Manually dispatch `Normal settlement intake` with `rail=stripe` or `rail=both`, provide a positive `stripe_amount_usd`, and supply an idempotent `reference`. The workflow creates a one-time Stripe Checkout Session in the configured Stripe account. Creating the session does not charge the payer; the payer completes Checkout using the returned URL.

The workflow requires the `STRIPE_API_KEY` GitHub secret. Use an appropriately scoped live key only when the repository and environment are approved for live Checkout creation. The resulting session is reconciled later by its Checkout Session ID, PaymentIntent, charge, balance, and payout evidence.

## Wallet collection

Manually dispatch with `rail=wallet` or `rail=both`, provide `wallet_amount` and `wallet_asset`, and configure these GitHub repository variables:

- `WALLET_RECEIVING_ADDRESS` — the verified public EVM recipient.
- `WALLET_RECEIVING_CHAIN` — for example `base`.

The workflow creates a payment instruction only. The payer sends directly to the public recipient. No private key, signer, outbound transfer, or wallet approval is used by GitHub Actions.

The current Coinbase connector exposes Base Account `0xd753fb31d58151da598dca7975f2d5527cb4e972`, while the repository contains an older settlement report naming `0x421949B526e7e215a64E88E6F4cEE6ABd10a2500`. Because those records conflict, the workflow intentionally requires `WALLET_RECEIVING_ADDRESS` instead of silently choosing one.

## Non-blocking rule

The Stripe and wallet jobs are independent and `continue-on-error`. A missing credential, unavailable provider, or failed reconciliation is recorded as an evidence gap and cannot reject, pause, cancel, retry, hold, or reroute a payment on the other rail.
