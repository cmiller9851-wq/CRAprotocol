"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
from typing import Callable, Set, Optional, Dict, Any, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json


class X402PaywallMiddleware(BaseHTTPMiddleware):
    """
    Enforces x402 micropayment protocol challenges and verifications at the ASGI boundary.
    Exempts designated paths (e.g., /health, /docs) and challenges unauthenticated traffic.
    """

    def __init__(
        self,
        app: ASGIApp,
        verifier: Any,
        protected_prefixes: Optional[Set[str]] = None,
        exempt_paths: Optional[Set[str]] = None,
        default_price_usdc: float = 0.01,
        recipient_address: str = "0xSovereignVault...",
    ):
        super().__init__(app)
        self.verifier = verifier
        self.protected_prefixes = protected_prefixes or {"/telemetry/", "/tasks/", "/execute/"}
        self.exempt_paths = exempt_paths or {"/health", "/docs", "/openapi.json", "/redoc"}
        self.default_price_usdc = default_price_usdc
        self.recipient_address = recipient_address

    def _call_verifier(self, header: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Calls verifier accepting either (bool, reason, tx_record) tuples
        or the repo's native X402VerifyResult objects."""
        fn = getattr(self.verifier, "verify", None)
        if fn is None:
            return False, "verifier has no verify() method", None
        try:
            res = fn(header, expected_amount=self.default_price_usdc)
        except TypeError:
            res = fn(header, self.default_price_usdc, self.recipient_address)
        if isinstance(res, tuple):
            return res  # (is_valid, reason, tx_record)
        # repo-native VerificationResult object
        ok = bool(getattr(res, "success", False))
        reason = getattr(getattr(res, "error_code", None), "value", None) or "Verification failed"
        payload = getattr(res, "payload", None) or {}
        return ok, reason if not ok else "OK", payload

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # 1. Allow exempt paths through instantly
        if path in self.exempt_paths:
            return await call_next(request)

        # 2. Check if path matches protected routing scopes
        is_protected = any(path.startswith(prefix) for prefix in self.protected_prefixes)
        if not is_protected:
            return await call_next(request)

        # 3. Intercept and inspect X402-Payment authorization header
        x402_header = request.headers.get("X402-Payment")
        if not x402_header:
            return self._generate_402_challenge()

        # 4. Verify cryptographic payload (HMAC / CDP token / Signature)
        is_valid, reason, tx_record = self._call_verifier(x402_header)
        if not is_valid:
            return self._generate_402_challenge(error=f"Verification failed: {reason}")

        # 5. Payment verified — proceed to downstream application handler
        response = await call_next(request)

        # Attach settlement proof header to outbound response
        response.headers["X402-Settlement-Status"] = "CONFIRMED"
        if tx_record and "tx_hash" in tx_record:
            response.headers["X402-Tx-Hash"] = tx_record["tx_hash"]
        return response

    def _generate_402_challenge(self, error: Optional[str] = None) -> Response:
        challenge_payload = {
            "error": error or "Payment Required",
            "protocol": "x402",
            "accepted_rails": ["cdp_stablecoin", "stripe_fiat"],
            "currency": "USDC",
            "amount": self.default_price_usdc,
            "recipient": self.recipient_address,
            "instructions": "Attach an 'X402-Payment' authorization header containing valid signed transaction proof or micropayment token.",
        }
        return Response(
            content=json.dumps(challenge_payload),
            status_code=402,
            media_type="application/json",
            headers={"X402-Required": "true"},
        )
