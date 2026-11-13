import sqlite3

import pytest

from cra_reference import CRALedger, StaticVerifier, canonicalize


def make_ledger():
    return CRALedger(sqlite3.connect(":memory:"), StaticVerifier())


def test_canonicalization_is_deterministic():
    assert canonicalize({"b": 2, "a": 1}) == b'{"a":1,"b":2}'


def test_verified_events_chain_to_l0():
    ledger = make_ledger()
    result = ledger.append(
        event_id="evt-1",
        event_time="2026-01-01T00:00:00Z",
        payload={"kind": "heartbeat", "counter": 1},
        signature=b"test-signature",
    )
    assert result.sequence == 1
    assert result.state == "VERIFIED"
    assert ledger.verify_chain()


def test_invalid_signature_is_quarantined():
    ledger = make_ledger()
    result = ledger.append(
        event_id="evt-invalid",
        event_time="2026-01-01T00:00:00Z",
        payload={"kind": "heartbeat"},
        signature=b"bad-signature",
    )
    assert result.state == "QUARANTINED"
    assert ledger.verify_chain()


def test_anomaly_threshold_is_quarantined():
    ledger = make_ledger()
    result = ledger.append(
        event_id="evt-anomaly",
        event_time="2026-01-01T00:00:00Z",
        payload={"kind": "telemetry"},
        signature=b"test-signature",
        anomaly_score=0.85,
    )
    assert result.state == "QUARANTINED"


def test_replayed_event_id_is_rejected():
    ledger = make_ledger()
    args = dict(
        event_id="evt-replay",
        event_time="2026-01-01T00:00:00Z",
        payload={"kind": "heartbeat"},
        signature=b"test-signature",
    )
    ledger.append(**args)
    with pytest.raises(ValueError, match="replayed"):
        ledger.append(**args)


def test_compensation_obligation_is_first_class():
    ledger = make_ledger()
    ledger.append(
        event_id="evt-license",
        event_time="2026-01-01T00:00:00Z",
        payload={"kind": "license_usage", "license": "SAEL-v1.0"},
        signature=b"test-signature",
    )
    ledger.add_compensation_obligation(
        obligation_id="ob-1",
        event_id="evt-license",
        creator_ref="creator:cory-miller",
        currency="USD",
        amount_minor=2500,
    )
    row = ledger.db.execute(
        "SELECT creator_ref, currency, amount_minor, status "
        "FROM compensation_obligations WHERE obligation_id = 'ob-1'"
    ).fetchone()
    assert row == ("creator:cory-miller", "USD", 2500, "pending")


def test_append_only_triggers_reject_mutation():
    ledger = make_ledger()
    result = ledger.append(
        event_id="evt-immutable",
        event_time="2026-01-01T00:00:00Z",
        payload={"kind": "heartbeat"},
        signature=b"test-signature",
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger.db.execute(
            "UPDATE ledger_events SET state = 'QUARANTINED' WHERE sequence = ?",
            (result.sequence,),
        )
