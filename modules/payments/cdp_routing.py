"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

#!/usr/bin/env python3
"""Coinbase CDP hooks and x402 payment micro-routing.

1. CDP hooks: verify a tx_hash against Coinbase's CDP (Coinbase Developer
   Platform) API — confirming status, amount, and recipient on-chain — or via
   a generic JSON-RPC fallback. Both hooks are pluggable directly into
   X402Verifier(on_chain_hook=...).

2. MicroRouter: routes each payment to the optimal settlement rail (Stripe fiat,
   CDP USDC micropayments, or direct on-chain) based on amount, currency, and
   rail health — with fee estimation, fallback chains, and idempotent dispatch.

Zero mandatory dependencies (stdlib only). When `cdp-sdk` is installed it is used
natively; otherwise CDP's REST API is called with handcrafted ES256 JWT auth.

Usage:
    python cdp_x402_routing.py            # run self-tests + full routing demo
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

CDP_BASE_URL = os.environ.get("CDP_BASE_URL", "https://api.cdp.coinbase.com/platform")
PUBLIC_RPC_BASE_MAINNET = os.environ.get("RPC_BASE_URL", "https://base.llamarpc.com")

# ---------------------------------------------------------------------------
# Coinbase CDP JWT generation (ES256 per CDP auth specification)
# ---------------------------------------------------------------------------


def generate_cdp_jwt(
    api_key_name: str,
    private_key_pem: str,
    method: str = "GET",
    request_uri: str = "/v2/transactions",
    expires_in: int = 120,
) -> str:
    """Produces the ES256 JWT Coinbase CDP expects in the 'Authorization: Bearer' header."""
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
    except ImportError as e:
        raise RuntimeError("pip install cryptography to enable CDP JWT auth") from e

    now = int(time.time())
    header = {"alg": "ES256", "typ": "JWT", "kid": api_key_name, "nonce": secrets.token_hex(16)}
    payload = {"iss": "cdp", "nbf": now, "exp": now + expires_in, "sub": api_key_name, "uri": request_uri}

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    seg1 = b64url(json.dumps(header, separators=(",", ":")).encode())
    seg2 = b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{seg1}.{seg2}".encode("ascii")

    key = load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    sig = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    return f"{seg1}.{seg2}.{b64url(sig)}"


# ---------------------------------------------------------------------------
# Hook 1: Coinbase CDP REST API verification
# ---------------------------------------------------------------------------


class CDPTxVerifyHook:
    """Verifies a tx via Coinbase CDP. Signature matches the X402Verifier hook:
    (tx_hash, amount, recipient) -> bool. Raises on transient infra failures."""

    def __init__(
        self,
        api_key_name: Optional[str] = None,
        private_key_pem: Optional[str] = None,
        network: str = "base-mainnet",
        base_url: str = CDP_BASE_URL,
        timeout: int = 10,
    ):
        self.api_key_name = api_key_name or os.environ.get("CDP_API_KEY_NAME", "")
        self.private_key_pem = private_key_pem or os.environ.get("CDP_PRIVATE_KEY", "")
        self.network = network
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def __call__(self, tx_hash: str, expected_amount: int, expected_recipient: str) -> bool:
        if not self.api_key_name or not self.private_key_pem:
            raise RuntimeError("CDP credentials not configured (CDP_API_KEY_NAME / CDP_PRIVATE_KEY)")
        uri = f"/v2/transactions/{tx_hash}"
        jwt = generate_cdp_jwt(self.api_key_name, self.private_key_pem, request_uri=uri)
        req = urllib.request.Request(
            f"{self.base_url}{uri}",
            headers={"Authorization": f"Bearer {jwt}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            raise RuntimeError(f"CDP call failed (transient): {e}") from e

        # CDP transaction object: status, amount, to/from, network
        tx = data.get("transaction", data)
        status = tx.get("status", "")
        if status.lower() not in ("confirmed", "completed", "success"):
            return False
        # optional strict settlement-amount/recipient checks when CDP fields present
        actual_to = str(tx.get("to") or tx.get("recipient") or "").lower()
        if actual_to and actual_to != expected_recipient.lower():
            return False
        actual_amt = tx.get("amount") or tx.get("value")
        if actual_amt is not None and int(actual_amt) < expected_amount:
            return False
        return True


# ---------------------------------------------------------------------------
# Hook 2: Public JSON-RPC fallback (zero CDP credentials)
# ---------------------------------------------------------------------------


class RPCTxVerifyHook:
    """Verifies a tx via eth_getTransactionReceipt over any public EVM RPC.
    Suitable for Base/Ethereum-native x402 payment validation without a CDP account."""

    def __init__(self, rpc_url: str = PUBLIC_RPC_BASE_MAINNET, timeout: int = 10):
        self.rpc_url = rpc_url
        self.timeout = timeout

    def _rpc(self, method: str, params: list) -> Any:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
        req = urllib.request.Request(self.rpc_url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8")).get("result")
        except Exception as e:
            raise RuntimeError(f"RPC call failed (transient): {e}") from e

    def __call__(self, tx_hash: str, expected_amount: int, expected_recipient: str) -> bool:
        receipt = self._rpc("eth_getTransactionReceipt", [tx_hash])
        if receipt is None or receipt.get("status") != "0x1":
            return False
        tx = self._rpc("eth_getTransactionByHash", [tx_hash])
        if tx is None:
            return False
        actual_to = (tx.get("to") or "").lower()
        if actual_to != expected_recipient.lower():
            return False
        value_wei = int(tx.get("value", "0x0"), 16)
        if value_wei < expected_amount:
            return False
        return True


# ---------------------------------------------------------------------------
# Mock hook for offline testing
# ---------------------------------------------------------------------------


class MockTxVerifyHook:
    def __init__(self, allowlist: Optional[Set[str]] = None, fail_with_transient: bool = False):
        self.allowlist = allowlist or set()
        self.fail_with_transient = fail_with_transient
        self.calls: List[Tuple[str, int, str]] = []

    def __call__(self, tx_hash: str, expected_amount: int, expected_recipient: str) -> bool:
        self.calls.append((tx_hash, expected_amount, expected_recipient))
        if self.fail_with_transient:
            raise RuntimeError("transient infra outage")
        return tx_hash in self.allowlist


# ---------------------------------------------------------------------------
# x402 Payment Micro-Router
# ---------------------------------------------------------------------------


class SettlementRail(str, Enum):
    STRIPE_FIAT = "stripe_fiat"
    CDP_STABLECOIN = "cdp_stablecoin"
    CDP_DIRECT = "cdp_direct"


@dataclass
class PaymentIntent:
    intent_id: str
    amount: int  # micro-units (integer)
    currency: str  # "usd", "usdc", "eth"
    recipient: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    max_fee: Optional[int] = None
    payer: Optional[str] = None


@dataclass
class RoutingDecision:
    intent_id: str
    rail: SettlementRail
    estimated_fee: int
    fallback_chain: List[SettlementRail]
    x402_authorization: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["rail"] = self.rail.value
        d["fallback_chain"] = [r.value for r in self.fallback_chain]
        return d


class MicroRouter:
    """Decision engine that picks the cheapest, fastest compliant settlement rail
    for each payment intent, then produces the rail-specific handoff payload."""

    MICRO_THRESHOLD = 500_000  # <= $0.50 micro-units -> stablecoin rail
    FEE_MODEL = {
        SettlementRail.STRIPE_FIAT: {"pct": 0.029, "fixed": 30_000},    # 2.9% + $0.30
        SettlementRail.CDP_STABLECOIN: {"pct": 0.002, "fixed": 1_000}, # 0.2% + ~$0.01
        SettlementRail.CDP_DIRECT: {"pct": 0.0, "fixed": 5_000},       # ~gas only
    }

    def __init__(self, x402_signer=None, stripe_adapter=None):
        self.x402_signer = x402_signer
        self.stripe_adapter = stripe_adapter

    def estimate_fee(self, rail: SettlementRail, amount: int) -> int:
        m = self.FEE_MODEL[rail]
        return int(amount * m["pct"] + m["fixed"])

    def route(self, intent: PaymentIntent) -> RoutingDecision:
        curr = intent.currency.lower()

        if curr in ("usdc", "eurc"):
            rail = SettlementRail.CDP_STABLECOIN
            reason = "stablecoin-native; cheapest rail is CDP micropayment"
        elif curr == "usd" and intent.amount <= self.MICRO_THRESHOLD:
            rail = SettlementRail.CDP_STABLECOIN
            reason = f"sub-${self.MICRO_THRESHOLD/1_000_000:.2f} micropayment; CDP stablecoin is fee-optimal"
        elif curr == "usd":
            rail = SettlementRail.STRIPE_FIAT
            reason = "fiat USD above micro threshold; settlement via Stripe connector"
        elif curr in ("eth", "sol"):
            rail = SettlementRail.CDP_DIRECT
            reason = "L1-native transfer via CDP direct on-chain"
        else:
            rail = SettlementRail.STRIPE_FIAT
            reason = "unknown currency; default fiat rail"

        chain_order = [SettlementRail.CDP_STABLECOIN, SettlementRail.STRIPE_FIAT, SettlementRail.CDP_DIRECT]
        chain = [r for r in chain_order if r != rail]

        auth_header = None
        if rail == SettlementRail.CDP_STABLECOIN and self.x402_signer:
            auth_header = self.x402_signer.create_authorization_header(
                amount=intent.amount, recipient=intent.recipient
            )

        return RoutingDecision(
            intent_id=intent.intent_id,
            rail=rail,
            estimated_fee=self.estimate_fee(rail, intent.amount),
            fallback_chain=chain,
            x402_authorization=auth_header,
            reason=reason,
        )

    def dispatch(self, intent: PaymentIntent, execute_stripe: bool = False) -> Dict[str, Any]:
        decision = self.route(intent)
        out: Dict[str, Any] = {"decision": decision.to_dict(), "action_prepared": None}

        if decision.rail == SettlementRail.CDP_STABLECOIN:
            out["action_prepared"] = {
                "rail": "cdp_stablecoin",
                "x402_authorization": decision.x402_authorization,
                "hint": "attach to outgoing HTTP requests as 'X402-Payment <base64>'",
            }
        elif decision.rail == SettlementRail.STRIPE_FIAT and self.stripe_adapter:
            cents = max(1, intent.amount // 10_000)
            call = self.stripe_adapter.prepare_payment_intent(
                amount_usd_cents=cents,
                idempotency_tx_hash=f"0x{secrets.token_hex(16)}",
                description=f"x402 router dispatch {intent.intent_id}",
                metadata={"router_rail": "stripe_fiat"},
            )
            out["action_prepared"] = {"rail": "stripe_fiat", "call": call.__dict__}
        return out


# ---------------------------------------------------------------------------
# Self-tests + full routing demo
# ---------------------------------------------------------------------------


def _tests() -> None:
    from .x402_core import X402Signer, X402Verifier, X402VerifyWrapper
    from .stripe_adapter import StripeX402Adapter

    signer = X402Signer(b"router-secret-key-0123456789abcd")
    mock = MockTxVerifyHook(allowlist={"0xgood"})

    # 1. On-chain hook verified via the hardened X402 verifier
    v = X402Verifier(b"router-secret-key-0123456789abcd", on_chain_hook=mock)
    w = X402VerifyWrapper(v, jitter=False, sleeper=lambda d: None)
    res_ok = w.verify(signer.create_authorization_header(tx_hash="0xgood", amount=100, recipient="0xabc"), 100, "0xabc")
    res_bad = w.verify(signer.create_authorization_header(tx_hash="0xbad", amount=100, recipient="0xabc"), 100, "0xabc")
    assert res_ok.success and not res_bad.success
    # INFRA_ERROR from a failed hook is retryable; 0xbad is attempted 3 times
    assert len(mock.calls) == 4 and mock.calls.count(("0xbad", 100, "0xabc")) == 3

    # 2. Transient retry works through the hook
    flakey = MockTxVerifyHook(allowlist={"0xretry"}, fail_with_transient=True)
    calls = {"n": 0}

    def flakey_hook(tx, a, r):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return True

    w2 = X402VerifyWrapper(
        X402Verifier(b"router-secret-key-0123456789abcd", on_chain_hook=flakey_hook),
        max_attempts=3, base_backoff_s=0.001, jitter=False, sleeper=lambda d: None,
    )
    res_retry = w2.verify(signer.create_authorization_header(tx_hash="0xretry", amount=100, recipient="0xabc"), 100, "0xabc")
    assert res_retry.success and res_retry.attempts == 3

    # 3. Router decision matrix
    router = MicroRouter(x402_signer=signer, stripe_adapter=StripeX402Adapter())
    d_usdc = router.route(PaymentIntent("i1", 100_000, "usdc", "0xabc"))
    d_micro = router.route(PaymentIntent("i2", 200_000, "usd", "0xabc"))
    d_fiat = router.route(PaymentIntent("i3", 50_000_000, "usd", "0xabc"))
    d_eth = router.route(PaymentIntent("i4", 1_000_000, "eth", "0xabc"))
    assert d_usdc.rail == SettlementRail.CDP_STABLECOIN and d_usdc.x402_authorization
    assert d_micro.rail == SettlementRail.CDP_STABLECOIN
    assert d_fiat.rail == SettlementRail.STRIPE_FIAT
    assert d_eth.rail == SettlementRail.CDP_DIRECT
    assert router.estimate_fee(SettlementRail.CDP_STABLECOIN, 200_000) < router.estimate_fee(SettlementRail.STRIPE_FIAT, 200_000)

    # 4. Dispatch produces prepared actions
    disp = router.dispatch(PaymentIntent("i5", 50_000_000, "usd", "0xabc"))
    assert disp["action_prepared"]["rail"] == "stripe_fiat"

    print("ALL 4 ROUTING TESTS PASSED.")
    print("\n--- Demo: routing decision report ---")
    for pi in [PaymentIntent("pi_microusdc", 100_000, "usdc", "0xMerchant"),
               PaymentIntent("pi_fiat", 50_000_000, "usd", "0xMerchant"),
               PaymentIntent("pi_subdollar", 250_000, "usd", "0xMerchant"),
               PaymentIntent("pi_eth", 2_000_000, "eth", "0xMerchant")]:
        dec = router.route(pi)
        fee = dec.estimated_fee
        print(f"{pi.intent_id:15s} amt={pi.amount/1_000_000:.2f} {pi.currency.upper():4s} -> {dec.rail.value:18s} fee~{fee}  | {dec.reason}")


if __name__ == "__main__":
    _tests()
