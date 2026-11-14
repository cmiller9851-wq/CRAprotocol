"""Permissionless payment-ingestion reference component.

The gateway accepts schema-valid envelopes without provider/account validation,
records them immediately as UNVERIFIED, preserves unknown sources under
UNATTRIBUTED, and exposes explicit downstream reconciliation transitions.
It never sends money, calls a provider, or treats an inbound payload as paid.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from .kernel import CRALedger, canonicalize, sha256_hex

_CURRENCY_RE = re.compile(r"^[A-Z0-9]{3,8}$")


@dataclass(frozen=True)
class InflowReceipt:
    inflow_id: str
    idempotency_key: str
    canonical_hash: str
    ledger_event_hash: str
    settlement_state: str
    attribution_state: str


class PermissionlessInflowGateway:
    """Open intake with fail-closed fulfillment semantics."""

    def __init__(self, ledger: CRALedger) -> None:
        self.ledger = ledger
        self.db = ledger.db
        self._configure()

    def _configure(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS inbound_inflows (
                inflow_id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                payment_reference TEXT NOT NULL,
                amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
                currency TEXT NOT NULL,
                source_ref TEXT,
                attribution_state TEXT NOT NULL CHECK
                    (attribution_state IN ('UNATTRIBUTED', 'ATTRIBUTED')),
                settlement_state TEXT NOT NULL CHECK
                    (settlement_state IN ('RECEIVED_UNVERIFIED', 'RECONCILING',
                                          'RECONCILED', 'QUARANTINED')),
                received_at TEXT NOT NULL,
                raw_payload BLOB NOT NULL,
                canonical_hash TEXT NOT NULL UNIQUE,
                ledger_event_hash TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS reconciliation_queue (
                inflow_id TEXT PRIMARY KEY,
                queued_at TEXT NOT NULL,
                queue_state TEXT NOT NULL CHECK
                    (queue_state IN ('PENDING', 'CLAIMED', 'DONE')),
                attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                FOREIGN KEY(inflow_id) REFERENCES inbound_inflows(inflow_id)
            );
            CREATE TABLE IF NOT EXISTS inflow_transitions (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                inflow_id TEXT NOT NULL,
                transition_time TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT NOT NULL,
                reason TEXT NOT NULL,
                transition_payload BLOB NOT NULL,
                parent_hash TEXT NOT NULL,
                transition_hash TEXT NOT NULL UNIQUE,
                FOREIGN KEY(inflow_id) REFERENCES inbound_inflows(inflow_id)
            );
            CREATE TRIGGER IF NOT EXISTS inflow_transitions_no_update
            BEFORE UPDATE ON inflow_transitions
            BEGIN SELECT RAISE(ABORT, 'inflow_transitions is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS inflow_transitions_no_delete
            BEFORE DELETE ON inflow_transitions
            BEGIN SELECT RAISE(ABORT, 'inflow_transitions is append-only'); END;
            CREATE INDEX IF NOT EXISTS idx_inflows_unattributed
                ON inbound_inflows(attribution_state, settlement_state);
            CREATE INDEX IF NOT EXISTS idx_queue_pending
                ON reconciliation_queue(queue_state, queued_at);
            """
        )
        self.db.commit()

    @staticmethod
    def _validate_envelope(
        *,
        provider: str,
        payment_reference: str,
        amount_minor: int,
        currency: str,
        payload: dict[str, Any],
        idempotency_key: str,
        received_at: str,
    ) -> None:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("provider is required")
        if not isinstance(payment_reference, str) or not payment_reference.strip():
            raise ValueError("payment_reference is required")
        if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or amount_minor < 0:
            raise ValueError("amount_minor must be a non-negative integer")
        if not isinstance(currency, str) or not _CURRENCY_RE.fullmatch(currency.upper()):
            raise ValueError("currency must be 3-8 uppercase alphanumeric characters")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if not isinstance(received_at, str) or not received_at.strip():
            raise ValueError("received_at is required")

    def _transition_tip(self) -> str:
        row = self.db.execute(
            "SELECT transition_hash FROM inflow_transitions ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return str(row[0]) if row else "INFLOW_L0_ROOT"

    def _record_transition(
        self,
        *,
        inflow_id: str,
        transition_time: str,
        from_state: str | None,
        to_state: str,
        reason: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        transition = {
            "inflow_id": inflow_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "extra": extra or {},
        }
        canonical = canonicalize(transition)
        parent_hash = self._transition_tip()
        transition_hash = sha256_hex(parent_hash.encode("ascii"), canonical)
        self.db.execute(
            """INSERT INTO inflow_transitions
            (inflow_id, transition_time, from_state, to_state, reason,
             transition_payload, parent_hash, transition_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                inflow_id,
                transition_time,
                from_state,
                to_state,
                reason,
                canonical,
                parent_hash,
                transition_hash,
            ),
        )
        return transition_hash

    def ingest(
        self,
        *,
        provider: str,
        payment_reference: str,
        amount_minor: int,
        currency: str,
        payload: dict[str, Any],
        idempotency_key: str,
        received_at: str,
        source_ref: str | None = None,
    ) -> InflowReceipt:
        """Accept a schema-valid payload without synchronous account validation."""

        self._validate_envelope(
            provider=provider,
            payment_reference=payment_reference,
            amount_minor=amount_minor,
            currency=currency,
            payload=payload,
            idempotency_key=idempotency_key,
            received_at=received_at,
        )
        normalized_currency = currency.upper()
        normalized_source = source_ref.strip() if isinstance(source_ref, str) and source_ref.strip() else None
        envelope = {
            "provider": provider.strip(),
            "payment_reference": payment_reference.strip(),
            "amount_minor": amount_minor,
            "currency": normalized_currency,
            "source_ref": normalized_source,
            "payload": payload,
        }
        canonical = canonicalize(envelope)
        canonical_hash = sha256_hex(canonical)
        existing = self.db.execute(
            """SELECT inflow_id, canonical_hash, ledger_event_hash,
                      settlement_state, attribution_state
               FROM inbound_inflows WHERE idempotency_key = ?""",
            (idempotency_key,),
        ).fetchone()
        if existing:
            if existing[1] != canonical_hash:
                raise ValueError("idempotency key conflict: payload differs")
            return InflowReceipt(
                existing[0], idempotency_key, existing[1], existing[2], existing[3], existing[4]
            )

        inflow_id = f"inflow-{sha256_hex(idempotency_key.encode(), canonical)[:24]}"
        event = self.ledger.append_unverified(
            event_id=inflow_id,
            event_time=received_at,
            payload={
                "kind": "payment_inflow",
                "inflow_id": inflow_id,
                "provider": provider.strip(),
                "payment_reference": payment_reference.strip(),
                "canonical_hash": canonical_hash,
                "attribution_state": "ATTRIBUTED" if normalized_source else "UNATTRIBUTED",
            },
        )
        attribution_state = "ATTRIBUTED" if normalized_source else "UNATTRIBUTED"
        self.db.execute(
            """INSERT INTO inbound_inflows
            (inflow_id, idempotency_key, provider, payment_reference,
             amount_minor, currency, source_ref, attribution_state,
             settlement_state, received_at, raw_payload, canonical_hash,
             ledger_event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'RECEIVED_UNVERIFIED', ?, ?, ?, ?)""",
            (
                inflow_id,
                idempotency_key,
                provider.strip(),
                payment_reference.strip(),
                amount_minor,
                normalized_currency,
                normalized_source,
                attribution_state,
                received_at,
                canonical,
                canonical_hash,
                event.event_hash,
            ),
        )
        self.db.execute(
            """INSERT INTO reconciliation_queue (inflow_id, queued_at, queue_state)
               VALUES (?, ?, 'PENDING')""",
            (inflow_id, received_at),
        )
        self._record_transition(
            inflow_id=inflow_id,
            transition_time=received_at,
            from_state=None,
            to_state="RECEIVED_UNVERIFIED",
            reason="accepted schema-valid inbound payload",
            extra={"attribution_state": attribution_state},
        )
        self.db.commit()
        return InflowReceipt(
            inflow_id,
            idempotency_key,
            canonical_hash,
            event.event_hash,
            "RECEIVED_UNVERIFIED",
            attribution_state,
        )

    def claim_reconciliation(self, *, limit: int = 10, claimed_at: str) -> list[str]:
        """Move pending records to RECONCILING for an asynchronous worker."""

        if limit < 1:
            raise ValueError("limit must be positive")
        self.db.execute("BEGIN IMMEDIATE")
        rows = self.db.execute(
            """SELECT q.inflow_id, i.settlement_state
               FROM reconciliation_queue q
               JOIN inbound_inflows i ON i.inflow_id = q.inflow_id
               WHERE q.queue_state = 'PENDING'
               ORDER BY q.queued_at, q.inflow_id LIMIT ?""",
            (limit,),
        ).fetchall()
        ids: list[str] = []
        for inflow_id, old_state in rows:
            self.db.execute(
                """UPDATE reconciliation_queue
                   SET queue_state = 'CLAIMED', attempts = attempts + 1
                   WHERE inflow_id = ?""",
                (inflow_id,),
            )
            self.db.execute(
                "UPDATE inbound_inflows SET settlement_state = 'RECONCILING' WHERE inflow_id = ?",
                (inflow_id,),
            )
            self._record_transition(
                inflow_id=inflow_id,
                transition_time=claimed_at,
                from_state=old_state,
                to_state="RECONCILING",
                reason="claimed by asynchronous reconciliation worker",
            )
            ids.append(inflow_id)
        self.db.commit()
        return ids

    def reconcile(
        self,
        *,
        inflow_id: str,
        verified: bool,
        reconciled_at: str,
        reason: str,
        source_ref: str | None = None,
    ) -> str:
        """Apply downstream evidence; unknown sources may remain unattributed."""

        row = self.db.execute(
            "SELECT settlement_state FROM inbound_inflows WHERE inflow_id = ?", (inflow_id,)
        ).fetchone()
        if not row:
            raise ValueError("unknown inflow_id")
        old_state = str(row[0])
        if old_state not in {"RECEIVED_UNVERIFIED", "RECONCILING"}:
            raise ValueError(f"inflow is not reconcilable from {old_state}")
        new_state = "RECONCILED" if verified else "QUARANTINED"
        normalized_source = source_ref.strip() if isinstance(source_ref, str) and source_ref.strip() else None
        attribution_state = "ATTRIBUTED" if normalized_source else None
        self.db.execute(
            """UPDATE inbound_inflows
               SET settlement_state = ?, source_ref = COALESCE(?, source_ref),
                   attribution_state = COALESCE(?, attribution_state)
               WHERE inflow_id = ?""",
            (new_state, normalized_source, attribution_state, inflow_id),
        )
        self.db.execute(
            "UPDATE reconciliation_queue SET queue_state = 'DONE' WHERE inflow_id = ?",
            (inflow_id,),
        )
        self._record_transition(
            inflow_id=inflow_id,
            transition_time=reconciled_at,
            from_state=old_state,
            to_state=new_state,
            reason=reason,
            extra={"verified": verified, "source_ref_supplied": bool(normalized_source)},
        )
        self.db.commit()
        return new_state

    def attribute(self, *, inflow_id: str, source_ref: str, attributed_at: str) -> None:
        """Map an already-recorded inflow without changing its settlement state."""

        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError("source_ref is required")
        row = self.db.execute(
            "SELECT settlement_state FROM inbound_inflows WHERE inflow_id = ?", (inflow_id,)
        ).fetchone()
        if not row:
            raise ValueError("unknown inflow_id")
        self.db.execute(
            """UPDATE inbound_inflows
               SET source_ref = ?, attribution_state = 'ATTRIBUTED'
               WHERE inflow_id = ?""",
            (source_ref.strip(), inflow_id),
        )
        self._record_transition(
            inflow_id=inflow_id,
            transition_time=attributed_at,
            from_state=str(row[0]),
            to_state=str(row[0]),
            reason="unknown source mapped asynchronously",
            extra={"source_ref": source_ref.strip()},
        )
        self.db.commit()

    def list_unattributed(self, *, limit: int = 100) -> list[sqlite3.Row | tuple[Any, ...]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        return self.db.execute(
            """SELECT inflow_id, provider, payment_reference, amount_minor,
                      currency, settlement_state, received_at, canonical_hash
               FROM inbound_inflows
               WHERE attribution_state = 'UNATTRIBUTED'
               ORDER BY received_at, inflow_id LIMIT ?""",
            (limit,),
        ).fetchall()

    def verify_transition_chain(self) -> bool:
        rows = self.db.execute(
            """SELECT transition_payload, parent_hash, transition_hash
               FROM inflow_transitions ORDER BY sequence"""
        ).fetchall()
        parent = "INFLOW_L0_ROOT"
        for canonical, parent_hash, transition_hash in rows:
            if parent_hash != parent:
                return False
            if sha256_hex(parent.encode("ascii"), canonical) != transition_hash:
                return False
            parent = transition_hash
        return True
