"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules.payments.middleware import X402PaywallMiddleware


class DummyVerifier:
    """Mock verifier for testing middleware settlement paths."""

    def verify(self, header_value: str, expected_amount: float):
        if header_value == "valid_token_123":
            return True, "OK", {"tx_hash": "0xabc123mockedtxhash"}
        elif header_value == "expired_token":
            return False, "Token expired", None
        return False, "Invalid signature", None


@pytest.fixture
def test_app():
    app = FastAPI()
    verifier = DummyVerifier()

    # Mount middleware
    app.add_middleware(
        X402PaywallMiddleware,
        verifier=verifier,
        protected_prefixes={"/api/"},
        exempt_paths={"/health"},
        default_price_usdc=0.01,
        recipient_address="0xTestVaultAddress",
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/resource")
    async def protected_resource():
        return {"data": "secured_payload_unlocked"}

    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


def test_health_check_bypass(client):
    """Exempt paths should pass through instantly without a 402 challenge."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X402-Required" not in response.headers


def test_protected_route_missing_header_emits_402(client):
    """Protected routes without an X402-Payment header must return HTTP 402 with challenge details."""
    response = client.post("/api/resource")
    assert response.status_code == 402
    assert response.headers.get("X402-Required") == "true"
    body = response.json()
    assert body["protocol"] == "x402"
    assert body["currency"] == "USDC"
    assert body["amount"] == 0.01
    assert body["recipient"] == "0xTestVaultAddress"
    assert "error" in body


def test_protected_route_invalid_header_emits_402(client):
    """An invalid payment token must be rejected with an appropriate 402 error message."""
    response = client.post(
        "/api/resource",
        headers={"X402-Payment": "bad_token"},
    )
    assert response.status_code == 402
    body = response.json()
    assert "Invalid signature" in body["error"]


def test_protected_route_valid_header_settles_and_passes(client):
    """A valid payment token must pass through successfully and attach settlement proof headers."""
    response = client.post(
        "/api/resource",
        headers={"X402-Payment": "valid_token_123"},
    )
    assert response.status_code == 200
    assert response.json() == {"data": "secured_payload_unlocked"}
    assert response.headers.get("X402-Settlement-Status") == "CONFIRMED"
    assert response.headers.get("X402-Tx-Hash") == "0xabc123mockedtxhash"
