# Quick Reference: Stripe Account Verification

## What is deployed

| File | Purpose |
|---|---|
| `stripe_payout_hold_release.py` | Queries Stripe and reports local evidence separately |
| `.github/workflows/stripe_hold_release.yml` | Scheduled/manual read-only verification workflow |
| `DIGITAL_CARDS_SETUP.md` | Full setup and security guidance |

## Configure secrets

In **Settings → Secrets and variables → Actions**, configure:

```text
STRIPE_API_KEY     = actual Stripe secret key
STRIPE_ACCOUNT_ID  = explicit account ID, for example acct_...
```

Keep both values in GitHub Secrets only. Never commit them or place them in documentation examples as if they were usable credentials.

## Workflow behavior

The workflow runs every six hours and supports manual execution. It:

1. Reads Stripe account requirements and enablement flags.
2. Reads available and pending balances.
3. Reads actual payouts, charges, and PaymentIntents.
4. Reads local CRA transaction/card evidence when available.
5. Records local provenance references separately.
6. Uploads a compliance report artifact.

It does **not** submit KYB, settlement, card, or Arweave metadata, and it does **not** request or claim payout-hold release.

## Evidence interpretation

| Status | Interpretation |
|---|---|
| `STRIPE_VERIFIED` | Directly supported by Stripe response data only. |
| `LOCAL_LEDGER_REPORTED` | Reported from the local CRA SQLite ledger; not Stripe settlement data. |
| `LOCAL_REFERENCE_RECORDED` | A local Arweave or provenance reference was recorded. |
| `NOT_SUBMITTED` | No KYB documents were submitted. |
| `NOT_SUPPORTED` | Payout-hold release is outside this repository's behavior. |

A PaymentIntent amount is not a receipt. Confirm payment only when Stripe reports a successful state and a positive `amount_received`.

## Run locally

```bash
python -m pip install requests
export STRIPE_API_KEY='(load securely; do not commit)'
export STRIPE_ACCOUNT_ID='acct_...'
python stripe_payout_hold_release.py
```

The command writes `/tmp/stripe_compliance_report.json` after querying live Stripe state. For offline testing, mock `requests.get`; no Stripe write request should occur.

## Artifact

GitHub Actions uploads:

```text
.github/workflows/artifacts/stripe_compliance_report.json
```

The report separates Stripe evidence, local CRA evidence, provenance, and verification status. Workflow execution alone is not proof of a Stripe payment, settlement, or payout release.

## Manual run

1. Open the repository **Actions** tab.
2. Select **Stripe Account Verification**.
3. Choose **Run workflow** on `main`.
4. Review the logs and download `stripe-compliance-report`.
