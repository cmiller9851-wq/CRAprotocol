# Affidavit Package — Repository & Evidence Checklist

Scope: This document is an index of repository and external evidence to assist verification; it is not a factual finding or legal opinion.

This document separates repository evidence (control and provenance) from external financial evidence. Each claim is tied to specific commits, PRs, and files to support independent verification.

## Repository control
- Repo: `cmiller9851-wq/CRAprotocol`  
  URL: https://github.com/cmiller9851-wq/CRAprotocol  
  Owner: `cmiller9851-wq`

- Repo: `cmiller9851-wq/patriot_palm_tree`  
  URL: https://github.com/cmiller9851-wq/patriot_palm_tree  
  Owner: `cmiller9851-wq`

## Representative commits (branch: `onboarding/new-contributor-surface`)
- 2d3061d0a7a59b536fb12dc82b4ba03b96cc5b9f — update to `CODE_OF_CONDUCT.md` (contact email)
- 1ee28b54814b34c3ee6d79ea55ce747572dcecdb — update to `SECURITY.md` (contact email)
- ca1a9cf3a8c9ff26b5943ba368b9c9646cae5a27 — Typst fix in `sovereign_proof/main.typ`
- 21248b12c51e5901a79f62525a8fb64b60a3535f — onboarding branch commit in `patriot_palm_tree`

## Pull requests
- cmiller9851-wq/CRAprotocol#7 — Add contributor onboarding + starter Phase A docs  
  URL: https://github.com/cmiller9851-wq/CRAprotocol/pull/7

- cmiller9851-wq/patriot_palm_tree#1 — Add contributor onboarding + starter Phase A docs  
  URL: https://github.com/cmiller9851-wq/patriot_palm_tree/pull/1

## Provenance & recommended hardening
- Signed commits or signed annotated tags provide the strongest non-repudiable provenance for repository artifacts. Recommended steps:
  - Create GPG-signed annotated tags for the branch tip(s) you consider authoritative:
    - git tag -s v0.1-onboarding <commit-sha> -m "Phase A onboarding snapshot"
    - git push origin --tags
  - Prefer GPG-signed commits for the final merge into main where possible.
- Note: commit signatures demonstrate authorship and integrity of commit contents but do not by themselves validate external factual claims.

## Financial evidence (must be provided separately)
If any affidavit claims refer to funds, custody, or settlements, include external records that match the same IDs/dates/amounts:
- Payment processor exports (e.g., Stripe) with matching payout IDs and dates
- Bank/custodial account statements covering the same transactions
- Any third-party attestations (signed emails or PDFs) from custodians or payment processors that corroborate the claims
- Cross-reference table mapping each monetary claim to the external evidence item (transaction ID, date, amount, file name)

## How to assemble the affidavit package
1. Narrative: short, dated statement of the claims being attested.
2. Repo evidence: links to repos, branch, commits, signed tags, PRs, reviewer/merge logs.
3. Financial evidence: PDFs/exports with a cross-reference table linking each claim to the matching external document.
4. Attestation: author-signed statement referencing the listed evidence (with date/time).

## Conclusion
Repo artifacts (ownership, commits, PRs, signed tags) provide verifiable evidence of control and authorship. External financial and custodial records are required to substantiate monetary claims. Keep repo evidence and financial evidence distinct and cross-referenced for efficient verification.
