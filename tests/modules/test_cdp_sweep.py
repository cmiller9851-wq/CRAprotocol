"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
import pytest
from modules.payments.cdp_sweep import (
    CdpSweepEngine,
    PRIMARY_WALLET,
    DEFAULT_SWEEP_DESTINATION,
    RESOLVED_DESTINATIONS,
    USDC_BASE,
    TRANSFER_SELECTOR,
)


def _engine(**kw):
    # offline mocks by default: simulate non-empty balance
    e = CdpSweepEngine(min_threshold_usdc=kw.pop("min_threshold_usdc", 5.0), keep_reserve_usdc=kw.pop("keep_reserve_usdc", 0.5), cooldown_seconds=kw.pop("cooldown_seconds", 600), dry_run=kw.pop("dry_run", True), **kw)
    e._eth_balance = lambda r, a: 0.1
    e._erc20_balance = lambda r, t, h, decimals=6: 25.5
    return e


def test_destination_resolution_cache():
    e = _engine()
    assert e.resolve_destination("cmiller.cb.id") == RESOLVED_DESTINATIONS["cmiller.cb.id"]
    assert e.resolve_destination("cmillerr.cb.id") == RESOLVED_DESTINATIONS["cmillerr.cb.id"]


def test_destination_resolution_raw_address():
    e = _engine()
    raw = "0x" + "ab"*20
    assert e.resolve_destination(raw).lower() == raw.lower()


def test_destination_resolution_unknown_raises():
    e = _engine()
    e._resolve_cb_id = lambda n: None
    with pytest.raises(ValueError):
        e.resolve_destination("nonexistent-name-xyz.example")


def test_build_transfer_encoding():
    e = _engine()
    dest = "0x" + "11"*20
    token, calldata, units = e.build_transfer(dest, 12.34)
    assert token == USDC_BASE
    assert calldata.startswith(TRANSFER_SELECTOR)
    assert units == 12340000
    # recipient zero-padded to 64 hex chars
    assert calldata[10:74] == dest[2:].zfill(64)
    # amount hex matches units
    assert int(calldata[74:138], 16) == units


def test_build_transfer_rejects_nonpositive():
    e = _engine()
    with pytest.raises(ValueError):
        e.build_transfer("0x" + "11"*20, 0.0)


def test_check_ready_and_not_ready():
    e = _engine()
    c = e.check()
    assert c["ready_to_sweep"] is True
    assert c["eligible_usdc"] == 25.0
    assert c["threshold_usdc"] == 5.0
    # when balance below threshold
    e._erc20_balance = lambda r, t, h, decimals=6: 3.0
    c = e.check()
    assert c["eligible_usdc"] == 2.5
    assert c["ready_to_sweep"] is False


def test_dry_run_sweep_simulation():
    e = _engine(sweep_destination="cmiller.cb.id")
    r = e.sweep()
    assert r["status"] == "simulated"
    assert r["mode"] == "dry-run"
    assert r["asset"] == "USDC_BASE"
    assert r["from"] == PRIMARY_WALLET
    assert r["to"] == RESOLVED_DESTINATIONS["cmiller.cb.id"]
    assert r["amount_usdc"] == 25.0
    assert r["tx_hash"].startswith("0xsim")
    assert r["calldata_preview"].startswith(TRANSFER_SELECTOR)
    assert len(e.sweep_ledger) == 1


def test_cooldown_enforcement():
    e = _engine(cooldown_seconds=3600)
    assert e.sweep()["status"] == "simulated"
    r2 = e.sweep()
    assert r2["status"] == "skipped"
    assert "threshold or cooldown" in r2["reason"]


def test_force_bypasses_cooldown():
    e = _engine(cooldown_seconds=3600)
    assert e.sweep()["status"] == "simulated"
    r = e.sweep(force=True)
    assert r["status"] == "simulated"
    assert len(e.sweep_ledger) == 2


def test_max_amount_caps_sweep():
    e = _engine()
    r = e.sweep(max_amount_usdc=10.0)
    assert r["amount_usdc"] == 10.0
    assert r["units"] == 10000000


def test_self_destination_warning_in_status():
    e = _engine(sweep_destination="cmillerr.cb.id")
    st = e.status()
    assert st["warning"] is not None
    assert "no-op" in st["warning"]


def test_status_fields():
    e = _engine()
    e.sweep()
    st = e.status()
    assert st["primary_wallet"] == PRIMARY_WALLET
    assert "-> " in st["sweep_destination"]
    assert st["total_swept_usdc"] == 25.0
    assert st["sweeps_count"] == 1
    assert st["last_sweep"] is not None
    assert st["mode"] == "dry-run"
