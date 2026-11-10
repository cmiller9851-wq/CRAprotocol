#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> [1/4] Running pytest test suite for middleware..."
PYTHONPATH=. pytest tests/modules/test_x402_middleware.py -v

echo "==> [2/4] Staging files in git..."
git add modules/payments/middleware.py
git add modules/payments/__init__.py
git add tests/modules/test_x402_middleware.py

echo "==> [3/4] Committing..."
git commit -m "feat(payments): add X402PaywallMiddleware for ASGI/FastAPI micro-settlement enforcement (SAEL v1.0)"

echo "==> [4/4] Pushing..."
git push -u origin "$(git branch --show-current)"

echo "==> Deployment of X402 Paywall Middleware complete!"
