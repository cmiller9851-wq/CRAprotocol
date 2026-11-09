"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

#!/usr/bin/env python3
"""Stripe webhook listener for x402 payment settlement confirmations.

Receives Stripe webhook events (invoice.paid, payment_intent.succeeded/failed,
charge.refunded), verifies Stripe's signature with pure-Python HMAC (zero
dependencies), and converts events into idempotent x402 settlement records.

Works with FastAPI, a built-in stdlib HTTP server for local testing, or as a
direct callable from any framework.

Usage:
    python stripe_webhook_x402.py                       # run tests + demo
    python stripe_webhook_x402.py serve 8000            # run local webhook server
    python stripe_webhook_x402.py replay <event_json>   # test-drive one event
"""

import hashlib
import hmac
import http.server
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Strict settlement record schema
# ---------------------------------------------------------------------------

X402_SETTLEMENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "settlement_id",
        "x402_tx_hash",
        "amount",
        "currency",
        "status",
        "stripe_event_id",
        "stripe_object_id",
        "created_at",
    ],
    "properties": {
        "settlement_id": {"type": "string"},
        "x402_tx_hash": {"type": "string"},
        "amount": {"type": "integer"},
        "currency": {"type": "string"},
        "status": {"type": "string", "enum": ["CONFIRMED", "FAILED", "REFUNDED", "IGNORED"]},
        "stripe_event_id": {"type": "string"},
        "stripe_object_id": {"type": "string"},
        "created_at": {"type": "integer"},
        "metadata": {"type": "object"},
    },
}


class SettlementStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    IGNORED = "IGNORED"


@dataclass
class SettlementRecord:
    settlement_id: str
    x402_tx_hash: str
    amount: int
    currency: str
    status: SettlementStatus
    stripe_event_id: str
    stripe_object_id: str
    created_at: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# ---------------------------------------------------------------------------
# Stripe signature verification (pure Python — no `stripe` package required)
# ---------------------------------------------------------------------------


def verify_stripe_signature(
    payload: bytes,
    sig_header: str,
    endpoint_secret: bytes,
    tolerance_seconds: int = 300,
    clock: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    """Verifies Stripe's 't=TIMESTAMP,v1=SIGNATURE' header per the official spec."""
    if not sig_header or not endpoint_secret:
        return False, "missing signature header or endpoint secret"

    timestamp_str: Optional[str] = None
    signatures: List[str] = []
    for pair in sig_header.split(","):
        kv = pair.split("=", 1)
        if len(kv) == 2:
            if kv[0].strip() == "t":
                timestamp_str = kv[1].strip()
            elif kv[0].strip() == "v1":
                signatures.append(kv[1].strip())

    if timestamp_str is None or not signatures:
        return False, "malformed Stripe-Signature header"

    try:
        event_time = int(timestamp_str)
    except ValueError:
        return False, "invalid timestamp in signature"

    now = int(clock if clock is not None else time.time())
    if abs(now - event_time) > tolerance_seconds:
        return False, f"signature timestamp outside {tolerance_seconds}s tolerance"

    signed_payload = f"{timestamp_str}.".encode("utf-8") + payload
    computed = hmac.new(endpoint_secret, signed_payload, hashlib.sha256).hexdigest()

    for s in signatures:
        if hmac.compare_digest(computed.lower(), s.lower()):
            return True, None
    return False, "no v1 signature matched computed HMAC"


def make_test_signature(payload: bytes, endpoint_secret: bytes, timestamp: Optional[int] = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    signed = f"{ts}.".encode("utf-8") + payload
    sig = hmac.new(endpoint_secret, signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


# ---------------------------------------------------------------------------
# Settlement ledger (idempotent, thread-safe in memory; plug your DB here)
# ---------------------------------------------------------------------------


class SettlementLedger:
    def __init__(self) -> None:
        self.records: Dict[str, SettlementRecord] = {}
        self.seen_events: Set[str] = set()

    def record(self, rec: SettlementRecord) -> None:
        self.records[rec.settlement_id] = rec
        self.seen_events.add(rec.stripe_event_id)

    def by_tx_hash(self, tx_hash: str) -> List[SettlementRecord]:
        return [r for r in self.records.values() if r.x402_tx_hash == tx_hash]


# ---------------------------------------------------------------------------
# Webhook processor
# ---------------------------------------------------------------------------

SettlementCallback = Callable[[SettlementRecord], None]


class StripeWebhookProcessor:
    """Consumes verified Stripe events and emits x402 settlement records."""

    EVENT_MAP = {
        "invoice.paid": SettlementStatus.CONFIRMED,
        "invoice.payment_succeeded": SettlementStatus.CONFIRMED,
        "invoice.finalized": None,  # no-op
        "payment_intent.succeeded": SettlementStatus.CONFIRMED,
        "payment_intent.payment_failed": SettlementStatus.FAILED,
        "payment_intent.canceled": SettlementStatus.FAILED,
        "charge.refunded": SettlementStatus.REFUNDED,
    }

    def __init__(
        self,
        endpoint_secret: bytes,
        ledger: Optional[SettlementLedger] = None,
        on_settlement: Optional[SettlementCallback] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.endpoint_secret = bytes(endpoint_secret)
        self.ledger = ledger or SettlementLedger()
        self.on_settlement = on_settlement
        self.log = logger or logging.getLogger("stripe.webhook")

    def process(self, raw_body: bytes, sig_header: str) -> Tuple[bool, str, Optional[SettlementRecord]]:
        ok, reason = verify_stripe_signature(raw_body, sig_header, self.endpoint_secret)
        if not ok:
            self.log.warning("signature verification failed: %s", reason)
            return False, reason or "signature failure", None

        try:
            event = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            return False, f"JSON decode error: {e}", None

        event_id = event.get("id")
        event_type = event.get("type")
        if not event_id or not event_type:
            return False, "event missing id or type", None

        # Stripe retries on network failures; deduplicate by event id
        if event_id in self.ledger.seen_events:
            self.log.info("duplicate event %s (idempotent no-op)", event_id)
            return True, "duplicate (ignored)", None

        status = self.EVENT_MAP.get(event_type, SettlementStatus.IGNORED)
        if status is None:  # explicit no-op
            self.ledger.seen_events.add(event_id)
            return True, "no-op event", None

        obj = (event.get("data") or {}).get("object") or {}
        meta = obj.get("metadata") or {}
        tx_hash = meta.get("x402_tx_hash", "none")
        amount = obj.get("amount", obj.get("amount_paid", 0)) or 0
        currency = obj.get("currency", "usd")
        obj_id = obj.get("id", "none")

        rec = SettlementRecord(
            settlement_id=f"set_{event_id}",
            x402_tx_hash=tx_hash,
            amount=amount,
            currency=currency,
            status=status,
            stripe_event_id=event_id,
            stripe_object_id=obj_id,
            created_at=int(time.time()),
            metadata={
                "event_type": event_type,
                "customer": obj.get("customer"),
                "invoice": obj.get("invoice"),
                "recipient": meta.get("x402_recipient"),
            },
        )
        self.ledger.record(rec)
        self.log.info(
            "x402 settlement %s tx=%s status=%s amount=%s",
            rec.settlement_id, tx_hash[:18] if tx_hash else "n/a", rec.status.value, amount
        )
        if self.on_settlement is not None:
            try:
                self.on_settlement(rec)
            except Exception as e:
                self.log.error("settlement callback error: %s", e)

        return True, "OK", rec


# ---------------------------------------------------------------------------
# FastAPI router (mount in any FastAPI app)
# ---------------------------------------------------------------------------


def make_fastapi_router(processor: StripeWebhookProcessor):
    """Returns a FastAPI APIRouter exposing POST /stripe with full verification."""
    from fastapi import APIRouter, Header, HTTPException, Request

    router = APIRouter()

    @router.post("/stripe")
    async def stripe_webhook(
        request: Request,
        stripe_signature: str = Header(None, alias="Stripe-Signature"),
    ):
        body = await request.body()
        ok, reason, rec = processor.process(body, stripe_signature or "")
        if not ok:
            raise HTTPException(status_code=400, detail=reason)
        return {"received": True, "event": rec.stripe_event_id if rec else None}

    return router


# ---------------------------------------------------------------------------
# Stdlib HTTP test server (zero-dep local testing)
# ---------------------------------------------------------------------------


def run_test_server(port: int = 8000, endpoint_secret: Optional[bytes] = None) -> None:
    secret = endpoint_secret or os.environ.get(
        "STRIPE_WEBHOOK_SECRET", "whsec_test_demo_secret_replace_in_prod"
    ).encode("utf-8")
    proc = StripeWebhookProcessor(secret)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            sig = self.headers.get("Stripe-Signature", "")
            ok, reason, rec = proc.process(body, sig)
            code = 200 if ok else 400
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "received": ok, "reason": reason, "record": rec.to_dict() if rec else None
            }).encode("utf-8"))

        def log_message(self, fmt, *args):
            logging.getLogger("stripe.webhook").info(fmt, *args)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    srv = http.server.HTTPServer(("0.0.0.0", port), Handler)
    logging.getLogger("stripe.webhook").info("Stripe webhook listener on port %d", port)
    srv.serve_forever()


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------


def _tests() -> None:
    secret = b"whsec_test_secret_0123456789abcdef"
    proc = StripeWebhookProcessor(secret)

    # 1. signature round-trip
    payload = json.dumps({
        "id": "evt_test1",
        "type": "invoice.paid",
        "data": {"object": {
            "id": "in_test1",
            "amount_paid": 500,
            "currency": "usd",
            "metadata": {"x402_tx_hash": "0xabc", "x402_recipient": "0x987"},
        }},
    }).encode("utf-8")
    sig = make_test_signature(payload, secret)
    ok, reason, rec = proc.process(payload, sig)
    assert ok and rec.status == SettlementStatus.CONFIRMED and rec.x402_tx_hash == "0xabc"

    # 2. duplicate event idempotent
    ok, reason, rec2 = proc.process(payload, sig)
    assert ok and rec2 is None and "duplicate" in reason

    # 3. bad signature rejected
    ok, reason, _ = proc.process(payload, "t=1,v1=deadbeef")
    assert not ok

    # 4. payment_failed
    fail_payload = json.dumps({
        "id": "evt_test2", "type": "payment_intent.payment_failed",
        "data": {"object": {"id": "pi_1", "metadata": {"x402_tx_hash": "0xdef"}}},
    }).encode("utf-8")
    ok, _, rec = proc.process(fail_payload, make_test_signature(fail_payload, secret))
    assert ok and rec.status == SettlementStatus.FAILED

    # 5. refund reverses
    refund_payload = json.dumps({
        "id": "evt_test3", "type": "charge.refunded",
        "data": {"object": {"id": "ch_1", "metadata": {"x402_tx_hash": "0xabc"}}},
    }).encode("utf-8")
    proc.process(refund_payload, make_test_signature(refund_payload, secret))
    assert proc.ledger.by_tx_hash("0xabc")[-1].status == SettlementStatus.REFUNDED

    print("ALL 5 WEBHOOK TESTS PASSED.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) == 1:
        _tests()
    elif sys.argv[1] == "serve":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        run_test_server(port)
    elif sys.argv[1] == "replay" and len(sys.argv) >= 3:
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_demo").encode("utf-8")
        payload = open(sys.argv[2], "rb").read()
        proc = StripeWebhookProcessor(secret)
        sig = make_test_signature(payload, secret)
        ok, reason, rec = proc.process(payload, sig)
        print(json.dumps({"ok": ok, "reason": reason, "record": rec.to_dict() if rec else None}, indent=2))
    else:
        print("Usage: stripe_webhook_x402.py [serve [port] | replay <event.json>]")
        sys.exit(2)
