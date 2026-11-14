"""Software-only CRA v2.0 reference kernel.

This module models canonical state, signature verification, append-only WAL
persistence, chain verification, replay protection, and quarantine. It does
not control hardware, PCIe, firmware, payment rails, or private keys.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Protocol

ANOMALY_THRESHOLD = 0.85


class SignatureVerifier(Protocol):
    def verify(self, payload: bytes, signature: bytes) -> bool:
        """Return True only when the signature is valid for the configured key."""


class RejectAllVerifier:
    """Safe default: no event is authorized without an injected verifier."""

    def verify(self, payload: bytes, signature: bytes) -> bool:
        return False


class StaticVerifier:
    """Deterministic test verifier; never use as a production verifier."""

    def __init__(self, accepted_signature: bytes = b"test-signature") -> None:
        self.accepted_signature = accepted_signature

    def verify(self, payload: bytes, signature: bytes) -> bool:
        return signature == self.accepted_signature


def canonicalize(value: Any) -> bytes:
    """Return deterministic JSON bytes for the reference boundary.

    A production deployment MUST replace this adapter with a conformant RFC
    8785 implementation. Python's standard JSON encoder is intentionally not
    presented as a complete JCS implementation.
    """

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(*parts: bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.hexdigest()


@dataclass(frozen=True)
class AppendResult:
    sequence: int
    event_hash: str
    state: str


class CRALedger:
    def __init__(self, connection: sqlite3.Connection, verifier: SignatureVerifier) -> None:
        self.db = connection
        self.verifier = verifier
        self._configure()

    def _configure(self) -> None:
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS ledger_events (
                sequence INTEGER PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE,
                event_time TEXT NOT NULL,
                canonical_payload BLOB NOT NULL,
                signature BLOB NOT NULL,
                parent_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL CHECK (state IN ('UNVERIFIED', 'VERIFIED', 'QUARANTINED', 'RECONCILING', 'RECONCILED')),
                anomaly_score REAL NOT NULL CHECK (anomaly_score >= 0 AND anomaly_score <= 1)
            );
            CREATE TABLE IF NOT EXISTS compensation_obligations (
                obligation_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                creator_ref TEXT NOT NULL,
                currency TEXT NOT NULL,
                amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
                status TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES ledger_events(event_id)
            );
            CREATE TRIGGER IF NOT EXISTS ledger_events_no_update
            BEFORE UPDATE ON ledger_events
            BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS ledger_events_no_delete
            BEFORE DELETE ON ledger_events
            BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
            """
        )
        self.db.commit()

    def _tip(self) -> tuple[int, str]:
        row = self.db.execute(
            "SELECT sequence, event_hash FROM ledger_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return (int(row[0]), str(row[1])) if row else (0, "L0_ROOT")

    def append(
        self,
        *,
        event_id: str,
        event_time: str,
        payload: dict[str, Any],
        signature: bytes,
        anomaly_score: float = 0.0,
        challenge: str | None = None,
    ) -> AppendResult:
        if not 0 <= anomaly_score <= 1:
            raise ValueError("anomaly_score must be between 0 and 1")
        if not event_id or not event_time:
            raise ValueError("event_id and event_time are required")
        if self.db.execute(
            "SELECT 1 FROM ledger_events WHERE event_id = ?", (event_id,)
        ).fetchone():
            raise ValueError("replayed event_id")

        envelope = dict(payload)
        if challenge is not None:
            envelope["challenge"] = challenge
        canonical = canonicalize(envelope)
        signature_ok = self.verifier.verify(canonical, signature)
        state = "VERIFIED" if signature_ok and anomaly_score < ANOMALY_THRESHOLD else "QUARANTINED"
        sequence, parent_hash = self._tip()
        next_sequence = sequence + 1
        event_hash = sha256_hex(
            parent_hash.encode("ascii"), canonical, signature
        )
        self.db.execute(
            """INSERT INTO ledger_events
            (sequence, event_id, event_time, canonical_payload, signature,
             parent_hash, event_hash, state, anomaly_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                next_sequence,
                event_id,
                event_time,
                canonical,
                signature,
                parent_hash,
                event_hash,
                state,
                anomaly_score,
            ),
        )
        self.db.commit()
        return AppendResult(next_sequence, event_hash, state)

    def append_unverified(
        self,
        *,
        event_id: str,
        event_time: str,
        payload: dict[str, Any],
    ) -> AppendResult:
        """Append a syntactically accepted event without claiming trust.

        This is the safe boundary for permissionless ingestion: the event is
        chained into the WAL immediately, but it has no signature and remains
        UNVERIFIED until a downstream reconciliation adapter produces evidence.
        """

        if not event_id or not event_time:
            raise ValueError("event_id and event_time are required")
        if self.db.execute(
            "SELECT 1 FROM ledger_events WHERE event_id = ?", (event_id,)
        ).fetchone():
            raise ValueError("replayed event_id")
        canonical = canonicalize(payload)
        sequence, parent_hash = self._tip()
        next_sequence = sequence + 1
        event_hash = sha256_hex(parent_hash.encode("ascii"), canonical, b"")
        self.db.execute(
            """INSERT INTO ledger_events
            (sequence, event_id, event_time, canonical_payload, signature,
             parent_hash, event_hash, state, anomaly_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'UNVERIFIED', 0.0)""",
            (
                next_sequence,
                event_id,
                event_time,
                canonical,
                b"",
                parent_hash,
                event_hash,
            ),
        )
        self.db.commit()
        return AppendResult(next_sequence, event_hash, "UNVERIFIED")

    def add_compensation_obligation(
        self,
        *,
        obligation_id: str,
        event_id: str,
        creator_ref: str,
        currency: str,
        amount_minor: int,
        status: str = "pending",
    ) -> None:
        if amount_minor < 0:
            raise ValueError("amount_minor must be non-negative")
        if not self.db.execute(
            "SELECT 1 FROM ledger_events WHERE event_id = ?", (event_id,)
        ).fetchone():
            raise ValueError("event_id does not exist")
        self.db.execute(
            """INSERT INTO compensation_obligations
            (obligation_id, event_id, creator_ref, currency, amount_minor, status)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (obligation_id, event_id, creator_ref, currency, amount_minor, status),
        )
        self.db.commit()

    def verify_chain(self) -> bool:
        rows = self.db.execute(
            """SELECT sequence, canonical_payload, signature, parent_hash, event_hash
            FROM ledger_events ORDER BY sequence"""
        ).fetchall()
        parent = "L0_ROOT"
        expected_sequence = 1
        for sequence, canonical, signature, parent_hash, event_hash in rows:
            if sequence != expected_sequence or parent_hash != parent:
                return False
            if sha256_hex(parent.encode("ascii"), canonical, signature) != event_hash:
                return False
            parent = event_hash
            expected_sequence += 1
        return True
