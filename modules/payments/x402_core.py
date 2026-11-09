"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

"""x402 Payment Module — client-side signing and hardened verification wrapper.

Strict-schema, standard-library-only implementation designed for Pythonista 3
and headless Python environments.
"""

import base64
import hashlib
import hmac
import json
import logging
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Strict schema declarations
# ---------------------------------------------------------------------------

X402_PAYLOAD_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["tx_hash", "amount", "recipient", "timestamp", "signature"],
    "properties": {
        "tx_hash": {"type": "string", "minLength": 1},
        "amount": {"type": "integer", "minimum": 1},
        "recipient": {"type": "string", "minLength": 1},
        "timestamp": {"type": "integer"},
        "signature": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    },
    "additionalProperties": False,
}

AUTHORIZATION_HEADER_PREFIX = "X402-Payment "

# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------


class X402ErrorCode(str, Enum):
    OK = "OK"
    INVALID_HEADER = "INVALID_HEADER"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    INSUFFICIENT_AMOUNT = "INSUFFICIENT_AMOUNT"
    RECIPIENT_MISMATCH = "RECIPIENT_MISMATCH"
    SIGNATURE_FAILED = "SIGNATURE_FAILED"
    REPLAY_TIMESTAMP = "REPLAY_TIMESTAMP"
    REPLAY_DOUBLE_SPEND = "REPLAY_DOUBLE_SPEND"
    INFRA_ERROR = "INFRA_ERROR"
    MAX_RETRIES_EXCEEDED = "MAX_RETRIES_EXCEEDED"


class X402TransientError(Exception):
    """Raised by optional infra hooks to trigger the wrapper's retry logic."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class X402Payload:
    tx_hash: str
    amount: int
    recipient: str
    timestamp: int
    signature: str

    def canonical_message(self) -> str:
        return f"{self.tx_hash}:{self.amount}:{self.recipient}:{self.timestamp}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    success: bool
    error_code: X402ErrorCode
    error_message: Optional[str]
    payload: Dict[str, Any]
    attempts: int
    latency_ms: float
    retried: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["error_code"] = self.error_code.value
        return d


@dataclass
class TelemetryEvent:
    event_name: str
    timestamp: int
    tx_hash: Optional[str]
    amount: Optional[int]
    recipient: Optional[str]
    success: bool
    error_code: str
    attempts: int
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


TelemetrySink = Callable[[TelemetryEvent], None]

# ---------------------------------------------------------------------------
# Client-side signing module
# ---------------------------------------------------------------------------


class X402Signer:
    """Produces specification-compliant X402-Payment authorization headers."""

    def __init__(self, secret_key: bytes, default_recipient: Optional[str] = None):
        if not isinstance(secret_key, (bytes, bytearray)) or len(secret_key) == 0:
            raise ValueError("secret_key must be non-empty bytes")
        self.secret_key = bytes(secret_key)
        self.default_recipient = default_recipient

    # -- core signing primitives -------------------------------------------

    def sign(
        self,
        tx_hash: Optional[str] = None,
        amount: int = 500_000,
        recipient: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> X402Payload:
        th = tx_hash or f"0x{uuid.uuid4().hex}"
        if not isinstance(th, str) or not th.strip():
            raise ValueError("tx_hash must be a non-empty string")
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError("amount must be a positive integer")
        rec = recipient if recipient is not None else self.default_recipient
        if not isinstance(rec, str) or not rec.strip():
            raise ValueError("recipient must be a non-empty string")
        ts = timestamp if timestamp is not None else int(time.time())

        message = f"{th}:{amount}:{rec}:{ts}"
        signature = hmac.new(
            self.secret_key, message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return X402Payload(
            tx_hash=th,
            amount=amount,
            recipient=rec,
            timestamp=ts,
            signature=signature,
        )

    # -- header encoding ----------------------------------------------------

    def encode_header(self, payload: X402Payload) -> str:
        raw = json.dumps(payload.to_dict(), separators=(",", ":")).encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        return f"{AUTHORIZATION_HEADER_PREFIX}{encoded}"

    def create_authorization_header(
        self,
        tx_hash: Optional[str] = None,
        amount: int = 500_000,
        recipient: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> str:
        """One-shot helper: sign + encode."""
        return self.encode_header(self.sign(tx_hash, amount, recipient, timestamp))

    # -- inspection helpers -------------------------------------------------

    @staticmethod
    def decode_header(header: str) -> Dict[str, Any]:
        """Parses an authorization header back to the signed payload dict."""
        if not isinstance(header, str) or not header.startswith(AUTHORIZATION_HEADER_PREFIX):
            raise ValueError("Invalid authorization scheme prefix")
        encoded = header[len(AUTHORIZATION_HEADER_PREFIX):]
        return json.loads(base64.b64decode(encoded, validate=True).decode("utf-8"))


# ---------------------------------------------------------------------------
# Hardened verifier (base verification function)
# ---------------------------------------------------------------------------


class X402Verifier:
    def __init__(
        self,
        secret_key: bytes,
        max_age_seconds: int = 300,
        seen_tx_hashes: Optional[Set[str]] = None,
        on_chain_hook: Optional[Callable[[str, int, str], bool]] = None,
    ):
        if not isinstance(secret_key, (bytes, bytearray)) or len(secret_key) == 0:
            raise ValueError("secret_key must be non-empty bytes")
        self.secret_key = bytes(secret_key)
        self.max_age_seconds = max_age_seconds
        self.seen_tx_hashes: Set[str] = seen_tx_hashes if seen_tx_hashes is not None else set()
        self.on_chain_hook = on_chain_hook

    def verify_once(
        self,
        auth_header: str,
        expected_amount: int,
        expected_recipient: str,
        clock: Optional[float] = None,
    ) -> Tuple[bool, X402ErrorCode, Optional[str], Dict[str, Any]]:
        if not isinstance(auth_header, str):
            return False, X402ErrorCode.INVALID_HEADER, "auth_header must be a string", {}

        parts = auth_header.strip().split(None, 1)
        if len(parts) != 2 or parts[0] != "X402-Payment":
            return False, X402ErrorCode.INVALID_HEADER, "Missing/invalid authorization scheme prefix", {}

        try:
            decoded = base64.b64decode(parts[1], validate=True)
            payload = json.loads(decoded.decode("utf-8"))
        except Exception as e:
            return False, X402ErrorCode.MALFORMED_PAYLOAD, f"Payload decode error: {e}", {}

        if not isinstance(payload, dict):
            return False, X402ErrorCode.MALFORMED_PAYLOAD, "Payload must be a JSON object", {}

        tx_hash = payload.get("tx_hash")
        amount = payload.get("amount")
        recipient = payload.get("recipient")
        timestamp = payload.get("timestamp")
        signature = payload.get("signature")

        if not isinstance(tx_hash, str) or not tx_hash.strip():
            return False, X402ErrorCode.SCHEMA_VIOLATION, "Invalid 'tx_hash'", payload
        if not isinstance(amount, int) or amount <= 0:
            return False, X402ErrorCode.SCHEMA_VIOLATION, "Invalid 'amount'", payload
        if not isinstance(recipient, str) or not recipient.strip():
            return False, X402ErrorCode.SCHEMA_VIOLATION, "Invalid 'recipient'", payload
        if not isinstance(timestamp, int):
            return False, X402ErrorCode.SCHEMA_VIOLATION, "Invalid 'timestamp'", payload
        if not isinstance(signature, str) or len(signature) != 64 or not all(c in "0123456789abcdef" for c in signature.lower()):
            return False, X402ErrorCode.SCHEMA_VIOLATION, "Invalid 'signature' format", payload

        now = int(clock if clock is not None else time.time())
        if abs(now - timestamp) > self.max_age_seconds:
            return False, X402ErrorCode.REPLAY_TIMESTAMP, f"Timestamp outside allowed window ({self.max_age_seconds}s)", payload

        if tx_hash in self.seen_tx_hashes:
            return False, X402ErrorCode.REPLAY_DOUBLE_SPEND, "tx_hash has already been used", payload

        if amount < expected_amount:
            return False, X402ErrorCode.INSUFFICIENT_AMOUNT, f"Insufficient payment: provided {amount}, required {expected_amount}", payload

        if recipient.lower() != expected_recipient.lower():
            return False, X402ErrorCode.RECIPIENT_MISMATCH, "Recipient address mismatch", payload

        message = f"{tx_hash}:{amount}:{recipient}:{timestamp}"
        computed = hmac.new(self.secret_key, message.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed.lower(), signature.lower()):
            return False, X402ErrorCode.SIGNATURE_FAILED, "Cryptographic signature validation failed", payload

        # Optional external on-chain hook (RPC/CDP call). Errors from this hook
        # are classified as transient and can be retried by the wrapper.
        if self.on_chain_hook is not None:
            try:
                ok = self.on_chain_hook(tx_hash, amount, recipient)
            except Exception as e:
                raise X402TransientError(f"on-chain verification failed: {e}") from e
            if not ok:
                return False, X402ErrorCode.INFRA_ERROR, "On-chain transaction verification failed", payload

        self.seen_tx_hashes.add(tx_hash)
        return True, X402ErrorCode.OK, None, payload


# ---------------------------------------------------------------------------
# Robust error-handling wrapper with retry logic and telemetry logging
# ---------------------------------------------------------------------------


class LoggingTelemetrySink:
    """Default telemetry sink: emits structured JSON lines via the logging module."""

    def __init__(self, logger_name: str = "x402.telemetry", level: int = logging.INFO):
        self.logger = logging.getLogger(logger_name)
        self.level = level

    def __call__(self, event: TelemetryEvent) -> None:
        self.logger.log(self.level, event.to_json())


class X402VerifyWrapper:
    """Wraps X402Verifier with exponential-backoff retry and structured telemetry.

    Retry policy: only *transient infrastructure errors* (e.g. RPC/CDP hook
    exceptions) are retried. Deterministic payment-level rejections
    (bad signature, replay, insufficient amount) fail fast on the first attempt
    — retrying them is both useless and dangerous.
    """

    def __init__(
        self,
        verifier: X402Verifier,
        max_attempts: int = 3,
        base_backoff_s: float = 0.25,
        max_backoff_s: float = 8.0,
        jitter: bool = True,
        telemetry_sinks: Optional[List[TelemetrySink]] = None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.verifier = verifier
        self.max_attempts = max_attempts
        self.base_backoff_s = base_backoff_s
        self.max_backoff_s = max_backoff_s
        self.jitter = jitter
        self.sleeper = sleeper
        self.telemetry_sinks: List[TelemetrySink] = (
            telemetry_sinks if telemetry_sinks is not None else [LoggingTelemetrySink()]
        )

    def _backoff(self, attempt: int) -> float:
        delay = min(self.base_backoff_s * (2 ** attempt), self.max_backoff_s)
        if self.jitter:
            delay = random.uniform(0, delay)
        return delay

    def _emit(self, event: TelemetryEvent) -> None:
        for sink in self.telemetry_sinks:
            try:
                sink(event)
            except Exception:
                pass  # telemetry failures must never break verification

    def verify(
        self,
        auth_header: str,
        expected_amount: int,
        expected_recipient: str,
        clock: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        start = time.perf_counter()
        last_error: Optional[str] = None
        last_payload: Dict[str, Any] = {}
        last_code: X402ErrorCode = X402ErrorCode.INFRA_ERROR

        for attempt in range(self.max_attempts):
            try:
                ok, code, error_msg, payload = self.verifier.verify_once(
                    auth_header, expected_amount, expected_recipient, clock=clock
                )
                last_code, last_error, last_payload = code, error_msg, payload

                # Terminal outcomes (deterministic success or rejection)
                if ok or code != X402ErrorCode.INFRA_ERROR:
                    result = VerificationResult(
                        success=ok,
                        error_code=code,
                        error_message=error_msg,
                        payload=payload,
                        attempts=attempt + 1,
                        latency_ms=(time.perf_counter() - start) * 1000.0,
                        retried=attempt > 0,
                    )
                    self._emit_event("verify_outcome", result, payload, metadata)
                    return result

            except X402TransientError as te:
                last_error = str(te)
                last_code = X402ErrorCode.INFRA_ERROR
                self._emit_retry_event(attempt + 1, str(te), metadata)

            except Exception as ue:  # unexpected runtime error — treat as infra
                last_error = f"unexpected error: {ue}"
                last_code = X402ErrorCode.INFRA_ERROR
                self._emit_retry_event(attempt + 1, str(ue), metadata)

            if attempt + 1 < self.max_attempts:
                self.sleeper(self._backoff(attempt))

        result = VerificationResult(
            success=False,
            error_code=X402ErrorCode.MAX_RETRIES_EXCEEDED,
            error_message=f"max retries exceeded; last error: {last_error}",
            payload=last_payload,
            attempts=self.max_attempts,
            latency_ms=(time.perf_counter() - start) * 1000.0,
            retried=True,
        )
        self._emit_event("verify_exhausted", result, last_payload, metadata)
        return result

    # -- telemetry helpers --------------------------------------------------

    def _emit_event(
        self,
        event_name: str,
        result: VerificationResult,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        self._emit(
            TelemetryEvent(
                event_name=event_name,
                timestamp=int(time.time()),
                tx_hash=payload.get("tx_hash"),
                amount=payload.get("amount"),
                recipient=payload.get("recipient"),
                success=result.success,
                error_code=result.error_code.value,
                attempts=result.attempts,
                latency_ms=round(result.latency_ms, 2),
                metadata=metadata or {},
            )
        )

    def _emit_retry_event(self, attempt: int, reason: str, metadata: Optional[Dict[str, Any]]) -> None:
        self._emit(
            TelemetryEvent(
                event_name="verify_retry",
                timestamp=int(time.time()),
                tx_hash=None,
                amount=None,
                recipient=None,
                success=False,
                error_code=X402ErrorCode.INFRA_ERROR.value,
                attempts=attempt,
                latency_ms=0.0,
                metadata={"reason": reason, **(metadata or {})},
            )
        )
