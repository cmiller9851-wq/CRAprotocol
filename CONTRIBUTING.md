# Purpose
This file gives new contributors a low-friction path to make meaningful, well-scoped changes without needing full knowledge of the deep architecture.

## Quick start (10-minute path)
1. Fork the repo and clone:
   - git clone git@github.com:<your-username>/<repo>.git
   - cd <repo>
2. Create a working branch:
   - git checkout -b onboarding/new-contributor-surface
3. Run setup:
   - ./dev-setup.sh
4. Pick an issue labeled good-first-module or help-wanted.
5. Make changes, add tests, run:
   - make test or python -m pytest
6. Open a PR using the .github/PULL_REQUEST_TEMPLATE.md and select the good-first-module label if applicable.

## Branching & commit conventions
- Branch name: module/<short-name> or onboarding/<your-name>/<task>
- Commit messages:
  - Short subject: 50 chars or less
  - Body: Why, what, notes about constraints (Patriot Protocol Hyper Beam, runtime)
  - Example: "module/account-cache: add basic skeleton and tests"

## PR checklist (authors)
- [ ] I ran the test suite locally (make test)
- [ ] I added/updated unit tests
- [ ] I added documentation where relevant (README, module README)
- [ ] My changes conform to module-spec (see MODULE_SPEC.md)
- [ ] CI passes (GitHub Actions)

## Reviewers
- Triage will apply these labels: good-first-module, help-wanted, needs-review, blocked, security.
- Requested reviewer should confirm:
  - Tests cover behavior & edge cases
  - No global state leaks (must use local/constrained state)
  - Concurrency-safe patterns enforced per module-spec

## Module-scope rules (short)
- Keep modules small and isolated: max ~300 lines logic (excluding tests).
- No direct network calls in unit tests; use injected interfaces or mocks.
- State mutations must be deterministic and produce a SHA-256 state root.

## Where to get help
- Open an issue with label help-wanted
- For private/security issues see SECURITY.md
