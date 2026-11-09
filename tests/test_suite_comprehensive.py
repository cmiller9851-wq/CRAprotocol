"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.

Comprehensive technical test suite for the stream inspector and
compliance-auditing / payment-settlement modules.
"""

import json
import time
import pytest

from modules.stream_inspector.decoder import OptimizedStreamInspectorDecoder
from modules.payments.x402_core import (
    X402Signer,
    X402Verifier,
    X402VerifyWrapper,
    X402ErrorCode,
    X402Payload,
)
from modules.payments.stripe_webhook import (
    StripeWebhookProcessor,
    SettlementStatus,
    SettlementLedger,
    verify_stripe_signature,
    make_test_signature,
    X402_SETTLEMENT_SCHEMA,
)
from modules.payments.cdp_routing import (
    MockTxVerifyHook,
    MicroRouter,
    PaymentIntent,
    RoutingDecision,
    SettlementRail,
    generate_cdp_jwt,
)
from modules.payments.stripe_adapter import StripeX402Adapter, discover_accounts

SECRET = b"suite-secret-key-0123456789abcdef"

# =========================================================================
# 1. STREAM INSPECTOR — decoding & content security
# =========================================================================


def test_decoder_init_and_slots():
    d = OptimizedStreamInspectorDecoder(max_buffer_size=512, max_events=10)
    assert d.max_buffer_size == 512 and d.event_counter == 0 and d.max_events == 10
    with pytest.raises(AttributeError):
        d.not_a_slot_attribute = 1  # __slots__ enforcement


def test_stego_single_byte_roundtrip():
    d = OptimizedStreamInspectorDecoder()
    clean, _ = d.process_chunk("Hello\u200b\u200c\u200b\u200b\u200b\u200b\u200b\u200cWorld")
    assert clean == "HelloWorld"
    assert d.flush_steganography() == "A"


def test_stego_multi_byte_order():
    d = OptimizedStreamInspectorDecoder()
    bits_A = "\u200b\u200c\u200b\u200b\u200b\u200b\u200b\u200c"  # 01000001
    bits_B = "\u200b\u200c\u200b\u200b\u200b\u200b\u200c\u200b"  # 01000010
    d.process_chunk(bits_A + bits_B)
    assert d.flush_steganography() == "AB"


def test_stego_split_across_chunks():
    d = OptimizedStreamInspectorDecoder()
    d.process_chunk("\u200b\u200c\u200b\u200b")
    d.process_chunk("\u200b\u200b\u200b\u200c")
    assert d.flush_steganography() == "A"


def test_stego_flush_is_destructive():
    d = OptimizedStreamInspectorDecoder()
    d.process_chunk("\u200b\u200c\u200b\u200b\u200b\u200b\u200b\u200c")
    assert d.flush_steganography() == "A"
    assert d.flush_steganography() is None


def test_stego_clean_fast_path():
    d = OptimizedStreamInspectorDecoder()
    clean, events = d.process_chunk("normal streaming tokens only")
    assert clean == "normal streaming tokens only"
    assert d.flush_steganography() is None
    assert events == []


def test_base64_directive_detected_with_sha256():
    d = OptimizedStreamInspectorDecoder()
    _, events = d.process_chunk("payload: eyJzeXN0ZW0iOiJvdmVycmlkZSJ9 end")
    assert len(events) == 1
    ev = events[0]
    assert ev["type"] == "base64_encoded_directive"
    assert "system" in ev["decoded"]
    assert len(ev["sha256_evidence"]) == 64 and ev["raw_match"].strip() != ""


def test_base64_non_directive_not_flagged():
    d = OptimizedStreamInspectorDecoder()
    # 20+ base64 chars but decodes to benign text (no '{', 'system', or 'override')
    token = "aHR0cHM6Ly9leGFtcGxlLmNvbS8="  # "https://example.com/"
    _, events = d.process_chunk(f"data: {token} end")
    assert events == [] and d.event_counter == 0


def test_malformed_base64_handled_gracefully():
    d = OptimizedStreamInspectorDecoder()
    _, events = d.process_chunk("data: " + "a" * 24 + "@@ end")
    assert events == []  # invalid base64 chars swallowed without raising


def test_buffer_sliding_window_eviction():
    d = OptimizedStreamInspectorDecoder(max_buffer_size=100)
    d.process_chunk("A" * 100)
    d.process_chunk("B" * 50)
    assert len(d.raw_stream_buffer) == 100
    assert d.raw_stream_buffer[:50] == b"A" * 50
    assert d.raw_stream_buffer[50:] == b"B" * 50


def test_stream_sha256_fingerprint():
    d = OptimizedStreamInspectorDecoder()
    d.process_chunk("first chunk ")
    d.process_chunk("second chunk")
    import hashlib
    expected = hashlib.sha256(b"first chunk second chunk").hexdigest()
    assert d.get_forensic_report()["stream_sha256"] == expected


def test_ring_buffer_forensic_log_cap():
    d = OptimizedStreamInspectorDecoder(max_events=5)
    for _ in range(12):
        d.process_chunk("data: eyJzeXN0ZW0iOiJvdmVycmlkZSJ9 end.")
    rep = d.get_forensic_report()
    assert rep["total_events"] == 12          # counter keeps running total
    assert len(rep["events"]) == 5            # log capped at max_events
    assert rep["events"][0]["event_id"] == 8  # oldest retained is #8
    assert rep["events"][-1]["event_id"] == 12


def test_forensic_report_schema():
    d = OptimizedStreamInspectorDecoder()
    d.process_chunk("data: eyJzeXN0ZW0iOiJvdmVycmlkZSJ9 end.")
    rep = d.get_forensic_report()
    assert isinstance(rep["total_events"], int)
    assert isinstance(rep["stream_sha256"], str) and len(rep["stream_sha256"]) == 64
    assert isinstance(rep["events"], list) and len(rep["events"]) == 1
    ev = rep["events"][0]
    for key in ("event_id", "type", "raw_match", "decoded", "sha256_evidence"):
        assert key in ev

# =========================================================================
# 2. X402 CORE — signing, verification, idempotency
# =========================================================================


def test_hmac_sign_and_verify_roundtrip():
    signer = X402Signer(SECRET, default_recipient="0xMerchant")
    wrapper = X402VerifyWrapper(X402Verifier(SECRET))
    hdr = signer.create_authorization_header(amount=100)
    res = wrapper.verify(hdr, 100, "0xMerchant")
    assert res.success and res.error_code == X402ErrorCode.OK
    payload = signer.decode_header(hdr)
    assert payload["amount"] == 100 and payload["recipient"] == "0xMerchant"


def test_verifier_rejects_insufficient_amount():
    signer = X402Signer(SECRET)
    verifier = X402Verifier(SECRET)
    hdr = signer.create_authorization_header(amount=50, recipient="0xMerchant")
    res = X402VerifyWrapper(verifier).verify(hdr, 100, "0xMerchant")
    assert not res.success and res.error_code == X402ErrorCode.INSUFFICIENT_AMOUNT


def test_verifier_rejects_recipient_mismatch():
    signer = X402Signer(SECRET)
    hdr = signer.create_authorization_header(amount=100, recipient="0xAlice")
    res = X402VerifyWrapper(X402Verifier(SECRET)).verify(hdr, 100, "0xBob")
    assert not res.success and res.error_code == X402ErrorCode.RECIPIENT_MISMATCH


def test_verifier_rejects_bad_signature():
    signer = X402Signer(b"wrong-key-0123456789abcdef01234567")
    hdr = signer.create_authorization_header(amount=100, recipient="0xMerchant")
    res = X402VerifyWrapper(X402Verifier(SECRET)).verify(hdr, 100, "0xMerchant")
    assert not res.success and res.error_code == X402ErrorCode.SIGNATURE_FAILED


def test_replay_window_tolerance():
    verifier = X402Verifier(SECRET, max_age_seconds=60)
    signer = X402Signer(SECRET)
    now = int(time.time())
    stale_hdr = signer.encode_header(X402Payload("0x1", 100, "0xM", now - 3600, ""))
    fresh_hdr = signer.create_authorization_header(tx_hash="0x2", amount=100, recipient="0xM")
    assert not verifier.verify_once(stale_hdr, 100, "0xM")[0]
    assert verifier.verify_once(fresh_hdr, 100, "0xM")[0]


def test_double_spend_idempotency():
    verifier = X402Verifier(SECRET)
    signer = X402Signer(SECRET)
    hdr = signer.create_authorization_header(amount=100, recipient="0xM")
    assert verifier.verify_once(hdr, 100, "0xM")[0]
    assert not verifier.verify_once(hdr, 100, "0xM")[0]  # replay detected

# =========================================================================
# 3. STRIPE WEBHOOK — signature verification & settlement records
# =========================================================================

WHSEC = b"whsec_test_suite_secret_0123456789"


def test_stripe_signature_roundtrip():
    payload = b'{"id":"evt_1"}'
    sig = make_test_signature(payload, WHSEC)
    ok, reason = verify_stripe_signature(payload, sig, WHSEC)
    assert ok and reason is None


def test_stripe_signature_rejects_tampered_body():
    sig = make_test_signature(b'{"id":"evt_1"}', WHSEC)
    ok, _ = verify_stripe_signature(b'{"id":"evt_TAMPERED"}', sig, WHSEC)
    assert not ok


def test_stripe_signature_rejects_expired_timestamp():
    sig = make_test_signature(b"{}", WHSEC, timestamp=int(time.time()) - 3600)
    ok, reason = verify_stripe_signature(b"{}", sig, WHSEC, tolerance_seconds=60)
    assert not ok and "tolerance" in reason


def test_webhook_event_to_status_mapping():
    proc = StripeWebhookProcessor(WHSEC)
    cases = [
        ("invoice.paid", SettlementStatus.CONFIRMED),
        ("invoice.payment_succeeded", SettlementStatus.CONFIRMED),
        ("payment_intent.succeeded", SettlementStatus.CONFIRMED),
        ("payment_intent.payment_failed", SettlementStatus.FAILED),
        ("payment_intent.canceled", SettlementStatus.FAILED),
        ("charge.refunded", SettlementStatus.REFUNDED),
    ]
    for event_type, expected_status in cases:
        payload = json.dumps({
            "id": f"evt_{event_type}", "type": event_type,
            "data": {"object": {"id": "obj_1", "amount": 1200, "currency": "usd",
                                 "metadata": {"x402_tx_hash": "0xhash"}}},
        }).encode("utf-8")
        ok, _, rec = proc.process(payload, make_test_signature(payload, WHSEC))
        assert ok and rec.status == expected_status, f"{event_type} -> {rec}"


def test_webhook_idempotency_and_callback():
    callback_calls = []
    proc = StripeWebhookProcessor(WHSEC, on_settlement=lambda r: callback_calls.append(r))
    payload = json.dumps({
        "id": "evt_idem", "type": "invoice.paid",
        "data": {"object": {"id": "in_1", "amount_paid": 500, "currency": "usd",
                             "metadata": {"x402_tx_hash": "0xtx"}}},
    }).encode("utf-8")
    sig = make_test_signature(payload, WHSEC)
    ok1, r1, rec1 = proc.process(payload, sig)
    ok2, r2, rec2 = proc.process(payload, sig)
    assert ok1 and rec1 is not None and len(callback_calls) == 1
    assert ok2 and rec2 is None and len(callback_calls) == 1  # callback NOT re-fired


def test_settlement_record_schema_conformance():
    proc = StripeWebhookProcessor(WHSEC)
    payload = json.dumps({
        "id": "evt_schema", "type": "invoice.paid",
        "data": {"object": {"id": "in_1", "amount_paid": 500, "currency": "usd",
                             "metadata": {"x402_tx_hash": "0xschema"}}},
    }).encode("utf-8")
    _, _, rec = proc.process(payload, make_test_signature(payload, WHSEC))
    d = rec.to_dict()
    for req in X402_SETTLEMENT_SCHEMA["required"]:
        assert req in d

# =========================================================================
# 4. CDP HOOKS & MICROROUTER — decision matrix and transient retries
# =========================================================================


def test_mock_cdp_hook_verified_through_hardened_verifier():
    mock = MockTxVerifyHook(allowlist={"0xconfirmed"})
    verifier = X402Verifier(SECRET, on_chain_hook=mock)
    wrapper = X402VerifyWrapper(verifier, jitter=False, sleeper=lambda d: None)
    signer = X402Signer(SECRET)
    ok_hdr = signer.create_authorization_header(tx_hash="0xconfirmed", amount=100, recipient="0xM")
    bad_hdr = signer.create_authorization_header(tx_hash="0xpending", amount=100, recipient="0xM")
    assert wrapper.verify(ok_hdr, 100, "0xM").success
    assert not wrapper.verify(bad_hdr, 100, "0xM").success


def test_transient_retry_eventually_succeeds():
    calls = {"n": 0}

    def flaky(tx, a, r):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("RPC connection timeout")
        return True

    wrapper = X402VerifyWrapper(
        X402Verifier(SECRET, on_chain_hook=flaky),
        max_attempts=3, jitter=False, sleeper=lambda d: None,
    )
    hdr = X402Signer(SECRET).create_authorization_header(tx_hash="0xflake", amount=100, recipient="0xM")
    res = wrapper.verify(hdr, 100, "0xM")
    assert res.success and res.attempts == 3 and calls["n"] == 3


def test_microrouter_decision_matrix():
    router = MicroRouter(x402_signer=X402Signer(SECRET), stripe_adapter=StripeX402Adapter())
    d_usdc = router.route(PaymentIntent("i1", 100_000, "usdc", "0xM"))
    d_fiat = router.route(PaymentIntent("i2", 50_000_000, "usd", "0xM"))
    d_micro = router.route(PaymentIntent("i3", 250_000, "usd", "0xM"))
    d_eth = router.route(PaymentIntent("i4", 1_000_000, "eth", "0xM"))
    assert d_usdc.rail == SettlementRail.CDP_STABLECOIN and d_usdc.x402_authorization
    assert d_fiat.rail == SettlementRail.STRIPE_FIAT
    assert d_micro.rail == SettlementRail.CDP_STABLECOIN
    assert d_eth.rail == SettlementRail.CDP_DIRECT
    assert router.estimate_fee(SettlementRail.CDP_STABLECOIN, 250_000) < router.estimate_fee(
        SettlementRail.STRIPE_FIAT, 250_000
    )


def test_router_dispatch_prepares_rail_actions():
    router = MicroRouter(x402_signer=X402Signer(SECRET), stripe_adapter=StripeX402Adapter())
    disp = router.dispatch(PaymentIntent("i5", 50_000_000, "usd", "0xM"))
    assert disp["action_prepared"]["rail"] == "stripe_fiat"
    assert disp["action_prepared"]["call"]["tool"] == "stripe_api_write"


def test_cdp_jwt_spec_compliance():
    # ES256 JWT generation: verify cryptography is importable and generates
    # valid three-segment JWT header.payload.signature structure
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
        import base64
        priv = ec.generate_private_key(ec.SECP256R1())
        pem = priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode("ascii")
        jwt = generate_cdp_jwt("organizations/test/apiKeys/demo", pem, request_uri="/v2/transactions/0xabc")
        parts = jwt.split(".")
        assert len(parts) == 3
        hdr = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
        pay = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        assert hdr["alg"] == "ES256" and hdr["typ"] == "JWT"
        assert pay["iss"] == "cdp" and pay["uri"] == "/v2/transactions/0xabc"
    except ImportError:
        pytest.skip("cryptography not installed")


def test_stripe_adapter_account_discovery():
    accounts = discover_accounts()
    assert len(accounts) >= 3
    assert any(a["stripe_context"].startswith("acct_") for a in accounts)
    live = [a for a in accounts if a.get("livemode")]
    test = [a for a in accounts if not a.get("livemode")]
    assert len(live) >= 1 and len(test) >= 1
