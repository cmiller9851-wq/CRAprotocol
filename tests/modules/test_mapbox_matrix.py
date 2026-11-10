"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
import pytest
from modules.telemetry import (
    TelemetryPoint,
    SpeedProfile,
    MapboxClient,
    DistanceMatrixProcessor,
    RouteCorridor,
    haversine_m,
    cross_track_distance_m,
    make_synthetic_fleet,
)


def test_haversine_known_distance():
    # NYC to LA ~ 3,944 km
    d = haversine_m(40.7128, -74.0060, 34.0522, -118.2437)
    assert 3_900_000 < d < 4_000_000


def test_cross_track_on_line():
    # collinear points along equator: cross-track should be ~0
    xtk = cross_track_distance_m(0.0, 1.0, 0.0, 0.0, 0.0, 2.0)
    assert xtk < 5.0  # meters tolerance


def test_speed_profile_computation():
    # 3 points, 10s intervals: A->B 100m, B->C dwell
    a = TelemetryPoint(40.0, -76.0, 100.0)
    # ~111m north: lat +0.001
    b = TelemetryPoint(40.001, -76.0, 110.0)
    c = TelemetryPoint(40.001, -76.0, 120.0)
    sp = SpeedProfile([a, b, c])
    assert len(sp.segments) == 2
    assert sp.segments[0].speed_mps > 10.0
    assert sp.segments[1].speed_mps == 0.0
    stats = sp.stats()
    assert stats.max_speed_mph > stats.mean_speed_mph
    assert stats.dwell_ratio > 0.0
    assert 0.0 <= stats.speeding_ratio <= 1.0


def test_speed_profile_requires_two_points():
    with pytest.raises(ValueError):
        SpeedProfile([TelemetryPoint(40.0, -76.0, 100.0)])


def test_geojson_export():
    fleet = make_synthetic_fleet(seed=7)
    sp = fleet["veh_0"]
    gj = sp.to_geojson()
    assert gj["type"] == "FeatureCollection"
    feat = gj["features"][0]
    assert feat["geometry"]["type"] == "LineString"
    assert feat["properties"]["point_count"] == len(sp.points)


def test_mapbox_client_mock_mode():
    client = MapboxClient(access_token=None)
    coords = [(-76.885, 40.297), (-76.840, 40.320), (-76.790, 40.340)]
    dirs = client.directions(coords)
    assert dirs["code"] == "Ok" and dirs["routes"][0]["distance"] > 0
    mat = client.matrix(coords)
    assert mat["code"] == "Ok"
    assert len(mat["durations"]) == 3


def test_distance_matrix_processor():
    client = MapboxClient()
    coords = [(-76.885, 40.297), (-76.840, 40.320), (-76.790, 40.340)]
    proc = DistanceMatrixProcessor(client.matrix(coords), labels=["A", "B", "C"])
    assert proc.nearest(0, k=2)[0][0] in ("B", "C")
    eta = proc.eta_matrix_minutes()
    assert eta[0][0] == 0.0 and eta[0][1] > 0
    assert proc.avg_outbound_duration(0) > 0


def test_congestion_anomaly_detection():
    # inject an artificially inflated duration between A and B
    client = MapboxClient()
    coords = [(-76.885, 40.297), (-76.840, 40.320)]
    mat = client.matrix(coords)
    mat["durations"][0][1] = 9999.0  # severe slowdown
    proc = DistanceMatrixProcessor(mat, labels=["A", "B"])
    anomalies = proc.congestion_anomalies(ratio_threshold=1.5)
    assert any(a.i == 0 and a.j == 1 for a in anomalies)


def test_route_corridor_conformance():
    route = [(-76.900, 40.300), (-76.850, 40.300), (-76.800, 40.300)]
    corridor = RouteCorridor(route, buffer_m=300.0)
    assert corridor.conforms(40.300, -76.875)           # on the line
    assert not corridor.conforms(40.350, -76.875)       # ~5.5 km away
    pts = [TelemetryPoint(40.300, -76.875, 1), TelemetryPoint(40.300, -76.860, 2)]
    assert corridor.conformance_ratio(pts) == 1.0


def test_synthetic_fleet_determinism():
    f1 = make_synthetic_fleet(seed=99)
    f2 = make_synthetic_fleet(seed=99)
    assert f1["veh_0"].stats().mean_speed_mph == f2["veh_0"].stats().mean_speed_mph
