# Digital Cards and Stripe Account Verification

## Scope

This repository contains two separate evidence sources:

1. **Local CRA evidence** — digital-card records, local transaction history, and provenance references.
2. **Stripe evidence** — the live account state returned by Stripe's API.

These sources must not be conflated. Local records do not prove a Stripe payment, settlement, payout, or compliance decision.

The Stripe workflow is **read-only with respect to Stripe compliance and settlement state**. It does not submit KYB data, post local settlement metadata, post card verification claims, post Arweave verification claims, or request payout-hold release.

## GitHub Actions secrets

Configure these repository secrets under **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `STRIPE_API_KEY` | The actual Stripe secret key, stored only in GitHub Secrets |
| `STRIPE_ACCOUNT_ID` | The explicit Stripe account being audited, for example `acct_...` |

Do not put either value in source files, documentation, command history, or workflow literals.

## Workflow

The workflow is [`.github/workflows/stripe_hold_release.yml`](.github/workflows/stripe_hold_release.yml) and runs every six hours or manually through `workflow_dispatch`.

It performs these read-only operations:

1. Query Stripe account restrictions, `charges_enabled`, `payouts_enabled`, `currently_due`, and `past_due`.
2. Query Stripe available and pending balances.
3. Query actual Stripe payouts, charges, and PaymentIntents.
4. Read local CRA settlement and digital-card records, if the local SQLite database is present in the execution environment.
5. Record provenance references without treating them as Stripe verification.
6. Export a compliance report artifact.

The report separates `stripe_evidence`, `local_cra_evidence`, `provenance`, and `verification_status`.

## Verification statuses

| Status | Meaning |
|---|---|
| `STRIPE_VERIFIED` | Reserved for facts directly returned by Stripe; the workflow does not manufacture this status. |
| `LOCAL_LEDGER_REPORTED` | Local SQLite transaction evidence only. |
| `LOCAL_REFERENCE_RECORDED` | Local Arweave/provenance reference only. |
| `NOT_SUBMITTED` | No KYB documents were submitted by this repository. |
| `NOT_SUPPORTED` | A payout-hold release request is not performed by this repository. |

A PaymentIntent is confirmed received only when Stripe reports an appropriate successful state and a positive `amount_received`; its existence or amount alone is not evidence of payment.

## Local testing

Install the only runtime dependency used by the Stripe script:

```bash
python -m pip install requests
```

The script requires both environment variables and performs live read-only Stripe queries:

```bash
export STRIPE_API_KEY='(load securely; do not commit)'
export STRIPE_ACCOUNT_ID='acct_...'
python stripe_payout_hold_release.py
```

For CI or offline testing, mock the `requests.get` calls. The script must not make Stripe `POST`, `PUT`, or `DELETE` calls.

## Report artifact

The workflow copies `/tmp/stripe_compliance_report.json` to `.github/workflows/artifacts/stripe_compliance_report.json` and uploads it as the `stripe-compliance-report` artifact. The artifact is evidence of what the workflow observed; it is not proof of a payout release or settlement unless Stripe's returned data supports that conclusion.

## Security

- Never commit Stripe API keys.
- Use the explicit account ID secret; do not infer or guess an account.
- Review the Stripe API response and the local CRA evidence separately.
- Do not describe local records, Arweave references, or workflow execution as Stripe-confirmed payments or settlements.
- Treat payout status as confirmed only from Stripe's actual account and payout responses.

## Related files

- `stripe_payout_hold_release.py` — read-only Stripe and local evidence reporter.
- `.github/workflows/stripe_hold_release.yml` — scheduled/manual verification workflow.
- `QUICK_REFERENCE.md` — concise operational reference.
