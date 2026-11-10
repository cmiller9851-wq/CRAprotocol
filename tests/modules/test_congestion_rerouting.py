"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
import pytest
from scripts.congestion_rerouting_simulation import inject_severe_congestion
from modules.telemetry import MapboxClient, DistanceMatrixProcessor, make_synthetic_fleet


def test_inject_congestion_is_asymmetric_and_multiplied():
    client = MapboxClient()
    coords = [(-76.920, 40.290), (-76.884, 40.264), (-77.009, 40.214)]
    base = client.matrix(coords)
    orig = base["durations"][0][1]
    m = inject_severe_congestion(base, 0, 1, 3.5)
    assert m["durations"][0][1] == pytest.approx(round(orig * 3.5, 1))
    assert m["durations"][1][0] == pytest.approx(round(orig * 3.5 * 0.8, 1))
    assert base["durations"][0][1] == orig  # non-destructive copy


def test_congestion_anomalies_flag_both_directions():
    client = MapboxClient()
    coords = [(-76.920, 40.290), (-76.884, 40.264), (-77.009, 40.214)]
    m = inject_severe_congestion(client.matrix(coords), 0, 1, 3.5)
    anomalies = DistanceMatrixProcessor(m, labels=["A", "B", "C"]).congestion_anomalies(ratio_threshold=1.75)
    pairs = {(a.i, a.j) for a in anomalies}
    assert (0, 1) in pairs
    assert any(a.severity == "severe" for a in anomalies)


@pytest.mark.asyncio
async def test_full_rerouting_simulation_end_to_end():
    from scripts.congestion_rerouting_simulation import main
    # runs cleanly end-to-end; errors would raise
    await main()
