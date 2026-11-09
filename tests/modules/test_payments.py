"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
import json
import sys

from modules.payments.x402_core import (
    X402Signer,
    X402Verifier,
    X402VerifyWrapper,
    X402ErrorCode,
)
from modules.payments.stripe_webhook import (
    StripeWebhookProcessor,
    make_test_signature,
    SettlementStatus,
)
from modules.payments.cdp_routing import (
    MockTxVerifyHook,
    MicroRouter,
    PaymentIntent,
    SettlementRail,
)
from modules.payments.stripe_adapter import StripeX402Adapter


def test_core_x402_sign_verify_happy():
    sec = b"test-secret-0123456789abcdef01234"
    signer = X402Signer(sec, default_recipient="0xabc")
    w = X402VerifyWrapper(X402Verifier(sec))
    hdr = signer.create_authorization_header(tx_hash="0xtx1", amount=100)
    res = w.verify(hdr, 100, "0xabc")
    assert res.success and res.error_code == X402ErrorCode.OK and res.attempts == 1


def test_webhook_event_flow():
    secret = b"whsec_test_secret_0123456789abcdef"
    proc = StripeWebhookProcessor(secret)
    payload = json.dumps({
        "id": "evt_t1",
        "type": "invoice.paid",
        "data": {"object": {"id": "in_1", "amount_paid": 500, "metadata": {"x402_tx_hash": "0xabc"}}},
    }).encode("utf-8")
    ok, _, rec = proc.process(payload, make_test_signature(payload, secret))
    assert ok and rec.status == SettlementStatus.CONFIRMED and rec.x402_tx_hash == "0xabc"
    ok2, r2, _ = proc.process(payload, make_test_signature(payload, secret))
    assert ok2 and "duplicate" in r2  # idempotent


def test_cdp_hook_and_router():
    sec = b"router-secret-key-0123456789abcd"
    signer = X402Signer(sec)
    mock = MockTxVerifyHook(allowlist={"0xgood"})
    w = X402VerifyWrapper(X402Verifier(sec, on_chain_hook=mock), jitter=False, sleeper=lambda d: None)
    res_ok = w.verify(signer.create_authorization_header(tx_hash="0xgood", amount=100, recipient="0xabc"), 100, "0xabc")
    res_bad = w.verify(signer.create_authorization_header(tx_hash="0xbad", amount=100, recipient="0xabc"), 100, "0xabc")
    assert res_ok.success and not res_bad.success

    router = MicroRouter(x402_signer=signer, stripe_adapter=StripeX402Adapter())
    assert router.route(PaymentIntent("i1", 100_000, "usdc", "0xabc")).rail == SettlementRail.CDP_STABLECOIN
    assert router.route(PaymentIntent("i2", 50_000_000, "usd", "0xabc")).rail == SettlementRail.STRIPE_FIAT
    assert router.route(PaymentIntent("i3", 200_000, "usd", "0xabc")).rail == SettlementRail.CDP_STABLECOIN


if __name__ == "__main__":
    for t in [test_core_x402_sign_verify_happy, test_webhook_event_flow, test_cdp_hook_and_router]:
        t()
        print(f"PASS {t.__name__}")
