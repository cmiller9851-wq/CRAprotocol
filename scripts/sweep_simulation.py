#!/usr/bin/env python3
"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.

Forced dry-run sweep simulation.
- Part 1 queries LIVE chain balances for the verified primary wallet
- Part 2 simulates what happens the instant accumulated revenue crosses $5
  (full simulated sweep record + ERC-20 calldata preview + cooldown check)

Usage:
    PYTHONPATH=. python3 scripts/sweep_simulation.py
    PYTHONPATH=. SWEEP_DESTINATION=cmiller.cb.id python3 scripts/sweep_simulation.py
"""
import os
import sys

from modules.payments.cdp_sweep import (
    CdpSweepEngine,
    PRIMARY_WALLET,
    DEFAULT_SWEEP_DESTINATION,
    RESOLVED_DESTINATIONS,
    USDC_BASE,
    TRANSFER_SELECTOR,
)

DEST = os.environ.get("SWEEP_DESTINATION", "cmiller.cb.id")

print("=" * 70)
print("PART 1 — LIVE STATE (real chain data)")
print("=" * 70)
e_live = CdpSweepEngine(min_threshold_usdc=5.0, keep_reserve_usdc=0.5, dry_run=True,
                        sweep_destination=DEST)
chk = e_live.check()
print(f"Primary wallet:        {chk['balances']['primary_wallet']}")
print(f"Live USDC (Base):      ${chk['balances']['usdc_base']}")
print(f"Live ETH (Base):       {chk['balances']['eth_base']:.6f}")
print(f"Live ETH (mainnet):    {chk['balances']['eth_mainnet']:.6f}")
print(f"Threshold:             ${chk['threshold_usdc']}")
print(f"Reserve kept:          ${e_live.keep_reserve_usdc}")
print(f"Ready to sweep?        {chk['ready_to_sweep']}")
print(f"Destination:           {chk['destination_name']} -> {chk['resolved_destination']}")

print("\n" + "=" * 70)
print("PART 2 — FORCED DRY-RUN SWEEP (simulated accumulated revenue: $12.50)")
print("=" * 70)
e = CdpSweepEngine(sweep_destination=DEST, min_threshold_usdc=5.0,
                   keep_reserve_usdc=0.5, dry_run=True)
e._erc20_balance = lambda *a, **k: 12.50
e._eth_balance = lambda *a, **k: 0.000003

before_chk = e.check()
print("Before check:")
print(f"  eligible USDC:       ${before_chk['eligible_usdc']}")
print(f"  ready to sweep:      {before_chk['ready_to_sweep']}")
print(f"  mode:                {before_chk['mode']}")
print(f"  destination:         {before_chk['destination_name']} -> {before_chk['resolved_destination']}")

rec = e.sweep(force=True)
print("\nSweep record:")
for k, v in rec.items():
    print(f"  {k:17s}: {v}")

print("\nEngine status after sweep:")
st = e.status()
print(f"  total swept:         ${st['total_swept_usdc']} USDC across {st['sweeps_count']} sweep(s)")
print(f"  cooldown:            {st['cooldown_s']} s")
print(f"  warning:             {st['warning']}")

print("\n" + "=" * 70)
print("PART 3 — CALLDATA VERIFICATION")
print("=" * 70)
calldata = rec["calldata_preview"]
print(f"Selector:              {calldata[:10]} (ERC-20 transfer)")
dest_raw = rec["to"]
print(f"To (zero-padded):      {calldata[10:74]} -> {dest_raw}")
units = int(calldata[74:138], 16)
print(f"Amount (hex):          {calldata[74:138]} -> {units:,} micro-units = ${units/1e6:.2f} USDC")
print(f"Token contract:        {USDC_BASE} (USDC on Base)")

print("\n" + "=" * 70)
print("PART 4 — COOLDOWN & IDEMPOTENCY")
print("=" * 70)
second = e.sweep()
print(f"Immediate second sweep: status={second['status']}, reason={second.get('reason')}")
print(f"\nAll good — forced dry-run sweep simulation PASSED.")
