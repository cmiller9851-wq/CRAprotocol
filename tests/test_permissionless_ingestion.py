import sqlite3

import pytest

from cra_reference import CRALedger, PermissionlessInflowGateway, StaticVerifier


def make_gateway():
    db = sqlite3.connect(":memory:")
    ledger = CRALedger(db, StaticVerifier())
    return PermissionlessInflowGateway(ledger), ledger


def inflow_args(**overrides):
    args = {
        "provider": "paypal",
        "payment_reference": "capture-001",
        "amount_minor": 2500,
        "currency": "usd",
        "payload": {"event_type": "payment.capture.completed", "opaque": "untrusted"},
        "idempotency_key": "idem-001",
        "received_at": "2026-01-01T00:00:00Z",
    }
    args.update(overrides)
    return args


def test_unknown_source_is_accepted_and_queued():
    gateway, ledger = make_gateway()
    receipt = gateway.ingest(**inflow_args())
    assert receipt.settlement_state == "RECEIVED_UNVERIFIED"
    assert receipt.attribution_state == "UNATTRIBUTED"
    assert gateway.claim_reconciliation(limit=1, claimed_at="2026-01-01T00:01:00Z") == [receipt.inflow_id]
    assert gateway.verify_transition_chain()
    assert ledger.verify_chain()
    assert gateway.list_unattributed()[0][0] == receipt.inflow_id


def test_idempotency_returns_same_receipt_and_conflicts_on_changed_payload():
    gateway, _ = make_gateway()
    first = gateway.ingest(**inflow_args())
    second = gateway.ingest(**inflow_args())
    assert second == first
    with pytest.raises(ValueError, match="idempotency key conflict"):
        gateway.ingest(**inflow_args(amount_minor=2600))


def test_reconciliation_can_close_without_attribution():
    gateway, _ = make_gateway()
    receipt = gateway.ingest(**inflow_args())
    gateway.claim_reconciliation(limit=1, claimed_at="2026-01-01T00:01:00Z")
    state = gateway.reconcile(
        inflow_id=receipt.inflow_id,
        verified=True,
        reconciled_at="2026-01-01T00:02:00Z",
        reason="provider evidence matched",
    )
    assert state == "RECONCILED"
    row = gateway.db.execute(
        "SELECT settlement_state, attribution_state FROM inbound_inflows WHERE inflow_id = ?",
        (receipt.inflow_id,),
    ).fetchone()
    assert row == ("RECONCILED", "UNATTRIBUTED")


def test_failed_reconciliation_quarantines_without_rejecting_intake():
    gateway, _ = make_gateway()
    receipt = gateway.ingest(**inflow_args())
    gateway.claim_reconciliation(limit=1, claimed_at="2026-01-01T00:01:00Z")
    assert gateway.reconcile(
        inflow_id=receipt.inflow_id,
        verified=False,
        reconciled_at="2026-01-01T00:02:00Z",
        reason="provider proof was not available",
    ) == "QUARANTINED"


def test_later_attribution_does_not_change_settlement_state():
    gateway, _ = make_gateway()
    receipt = gateway.ingest(**inflow_args())
    gateway.attribute(
        inflow_id=receipt.inflow_id,
        source_ref="customer:known-later",
        attributed_at="2026-01-01T00:03:00Z",
    )
    row = gateway.db.execute(
        "SELECT settlement_state, attribution_state, source_ref FROM inbound_inflows WHERE inflow_id = ?",
        (receipt.inflow_id,),
    ).fetchone()
    assert row == ("RECEIVED_UNVERIFIED", "ATTRIBUTED", "customer:known-later")


def test_schema_guard_is_not_provider_account_validation():
    gateway, _ = make_gateway()
    with pytest.raises(ValueError, match="amount_minor"):
        gateway.ingest(**inflow_args(amount_minor=-1))
    receipt = gateway.ingest(**inflow_args(provider="unknown-provider"))
    assert receipt.settlement_state == "RECEIVED_UNVERIFIED"
