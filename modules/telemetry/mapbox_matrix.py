"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.

Mapbox telemetry and speed matrix processing pipeline.

- Mapbox Directions & Matrix API client (token-optional mock mode for offline testing)
- Telemetry track ingestion with instantaneous speed calculation and dwell detection
- Distance/duration matrix processing: nearest-neighbor pairing, congestion anomaly flags
- Route corridors (cross-track distance) for spatial geofence conformance
- GeoJSON FeatureCollection export
"""

import json
import logging
import math
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

MAPBOX_BASE = "https://api.mapbox.com"
EARTH_RADIUS_M = 6_371_000.0


# ---------------------------------------------------------------------------
# Geodesic math (stdlib only)
# ---------------------------------------------------------------------------


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two lat/lon points."""
    r1, r2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(r1) * math.cos(r2) * math.sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def cross_track_distance_m(
    pt_lat: float, pt_lon: float,
    a_lat: float, a_lon: float,
    b_lat: float, b_lon: float,
) -> float:
    """Approximate distance (meters) of a point from the great-circle segment AB."""
    d_ap = haversine_m(a_lat, a_lon, pt_lat, pt_lon)
    if d_ap < 1e-3:
        return 0.0
    r_ap = d_ap / EARTH_RADIUS_M
    # bearing A->P and A->B
    brg_ap = math.atan2(
        math.sin(math.radians(pt_lon - a_lon)) * math.cos(math.radians(pt_lat)),
        math.cos(math.radians(a_lat)) * math.sin(math.radians(pt_lat)) -
        math.sin(math.radians(a_lat)) * math.cos(math.radians(pt_lat)) * math.cos(math.radians(pt_lon - a_lon)),
    )
    brg_ab = math.atan2(
        math.sin(math.radians(b_lon - a_lon)) * math.cos(math.radians(b_lat)),
        math.cos(math.radians(a_lat)) * math.sin(math.radians(b_lat)) -
        math.sin(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.cos(math.radians(b_lon - a_lon)),
    )
    xtk = math.asin(math.sin(r_ap) * math.sin(brg_ap - brg_ab))
    return abs(xtk * EARTH_RADIUS_M)


# ---------------------------------------------------------------------------
# Telemetry ingestion & speed profiling
# ---------------------------------------------------------------------------


@dataclass
class TelemetryPoint:
    lat: float
    lon: float
    timestamp: float  # epoch seconds

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpeedSegment:
    from_point: TelemetryPoint
    to_point: TelemetryPoint
    distance_m: float
    duration_s: float
    speed_mps: float
    speed_mph: float


@dataclass
class SpeedStats:
    point_count: int
    duration_s: float
    total_distance_m: float
    mean_speed_mph: float
    p95_speed_mph: float
    max_speed_mph: float
    dwell_ratio: float      # fraction of duration spent stationary (<1.0 m/s)
    speeding_ratio: float   # fraction of duration above speed limit

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SpeedProfile:
    """Computes instantaneous speeds between successive telemetry fixes and
    derives fleet-level speed statistics."""

    DWELL_THRESHOLD_MPS = 1.0  # ~2.2 mph — stationary

    def __init__(self, points: List[TelemetryPoint]):
        if len(points) < 2:
            raise ValueError("a telemetry track requires at least 2 points")
        # enforce chronological order
        self.points = sorted(points, key=lambda p: p.timestamp)
        self.segments: List[SpeedSegment] = []
        self._compute_segments()

    def _compute_segments(self) -> None:
        for a, b in zip(self.points, self.points[1:]):
            dt = b.timestamp - a.timestamp
            if dt <= 0:
                continue
            dist = haversine_m(a.lat, a.lon, b.lat, b.lon)
            mps = dist / dt
            self.segments.append(SpeedSegment(
                from_point=a, to_point=b, distance_m=dist, duration_s=dt,
                speed_mps=mps, speed_mph=mps * 2.23694,
            ))

    def stats(self, speed_limit_mph: float = 65.0) -> SpeedStats:
        if not self.segments:
            return SpeedStats(len(self.points), 0, 0, 0, 0, 0, 0, 0)
        total_time = sum(s.duration_s for s in self.segments)
        total_dist = sum(s.distance_m for s in self.segments)
        speeds = [s.speed_mph for s in self.segments]
        sorted_s = sorted(speeds)
        p95 = sorted_s[int(len(sorted_s) * 0.95)]
        dwell_time = sum(s.duration_s for s in self.segments if s.speed_mps < self.DWELL_THRESHOLD_MPS)
        speeding_time = sum(s.duration_s for s in self.segments if s.speed_mph > speed_limit_mph)
        return SpeedStats(
            point_count=len(self.points),
            duration_s=round(total_time, 2),
            total_distance_m=round(total_dist, 2),
            mean_speed_mph=round(mean(speeds), 2),
            p95_speed_mph=round(p95, 2),
            max_speed_mph=round(max(speeds), 2),
            dwell_ratio=round(dwell_time / total_time, 4),
            speeding_ratio=round(speeding_time / total_time, 4),
        )

    def to_geojson(self) -> Dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[p.lon, p.lat] for p in self.points],
                },
                "properties": self.stats().to_dict(),
            }],
        }


# ---------------------------------------------------------------------------
# Mapbox client (Directions & Matrix APIs)
# ---------------------------------------------------------------------------


class MapboxClient:
    """Thin wrapper over Mapbox Directions and Matrix APIs with retry handling
    and an offline synthetic-mock mode when no access token is configured."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        base_url: str = MAPBOX_BASE,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.token = access_token if access_token is not None else os.environ.get("MAPBOX_ACCESS_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.log = logging.getLogger("cra.mapbox")

    def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        params = dict(params or {})
        params["access_token"] = self.token
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.base_url}{path}?{qs}"
        last_exc: Exception = RuntimeError("no attempts")
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "CRA-telemetry/1.0"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                last_exc = e
                if e.code in (429, 500, 502, 503):
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise
            except Exception as e:
                last_exc = e
                time.sleep(0.5 * (2 ** attempt))
        raise RuntimeError(f"Mapbox request failed after {self.max_retries} attempts: {last_exc}")

    def directions(
        self,
        coordinates: List[Tuple[float, float]],
        profile: str = "driving",
        annotations: str = "distance,duration,speed",
    ) -> Dict[str, Any]:
        """coordinates: list of (lon, lat) pairs per Mapbox spec."""
        if not self.token:
            return self._mock_directions(coordinates)
        coord_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        return self._get(
            f"/directions/v5/mapbox/{profile}/{coord_str}",
            {"geometries": "geojson", "overview": "full", "annotations": annotations},
        )

    def matrix(
        self,
        coordinates: List[Tuple[float, float]],
        profile: str = "driving",
        annotations: str = "distance,duration",
    ) -> Dict[str, Any]:
        """Returns distance (m) and duration (s) matrices for NxN coordinates."""
        if not self.token:
            return self._mock_matrix(coordinates)
        coord_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        return self._get(f"/directions-matrix/v1/mapbox/{profile}/{coord_str}", {"annotations": annotations})

    @staticmethod
    def _mock_matrix(coordinates: List[Tuple[float, float]]) -> Dict[str, Any]:
        """Synthetic matrix from haversine distances assuming 13.4 m/s (~30 mph)."""
        n = len(coordinates)
        dist = [[haversine_m(a[1], a[0], b[1], b[0]) for b in coordinates] for a in coordinates]
        dur = [[round(dist[i][j] / 13.4, 1) for j in range(n)] for i in range(n)]
        return {"code": "Ok", "durations": dur, "distances": [[round(d, 1) for d in row] for row in dist]}

    @staticmethod
    def _mock_directions(coordinates: List[Tuple[float, float]]) -> Dict[str, Any]:
        total_dist = sum(
            haversine_m(a[1], a[0], b[1], b[0])
            for a, b in zip(coordinates, coordinates[1:])
        )
        return {
            "code": "Ok",
            "routes": [{
                "distance": round(total_dist, 1),
                "duration": round(total_dist / 13.4, 1),
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }],
        }


# ---------------------------------------------------------------------------
# Distance / duration matrix processing
# ---------------------------------------------------------------------------


@dataclass
class MatrixAnomaly:
    i: int
    j: int
    actual_duration_s: float
    implied_duration_s: float
    ratio: float
    severity: str  # "mild", "severe"


class DistanceMatrixProcessor:
    """Analyzes a Mapbox Matrix API response: nearest neighbors, ETA table,
    and congestion anomalies where duration far exceeds distance-implied time."""

    def __init__(self, matrix_payload: Dict[str, Any], labels: Optional[List[str]] = None):
        if matrix_payload.get("code") != "Ok":
            raise ValueError(f"matrix response error: {matrix_payload.get('code')}")
        self.durations: List[List[float]] = matrix_payload.get("durations", [])
        self.distances: List[List[float]] = matrix_payload.get("distances", [])
        self.n = len(self.durations)
        self.labels = labels or [f"n{i}" for i in range(self.n)]

    def nearest(self, i: int, k: int = 3, metric: str = "duration") -> List[Tuple[str, float]]:
        """K nearest neighbors by 'duration' (s) or 'distance' (m)."""
        mat = self.durations if metric == "duration" else self.distances
        row = [(self.labels[j], mat[i][j]) for j in range(self.n) if j != i and mat[i][j] is not None]
        return sorted(row, key=lambda r: r[1])[:k]

    def eta_matrix_minutes(self) -> List[List[float]]:
        return [[round(d / 60.0, 1) if d is not None else -1 for d in row] for row in self.durations]

    def congestion_anomalies(self, expected_speed_mph: float = 30.0, ratio_threshold: float = 1.75) -> List[MatrixAnomaly]:
        """Flags origin-destination pairs where actual duration is >= ratio_threshold
        times the duration implied by straight-line distance at expected_speed_mph."""
        expected_mps = expected_speed_mph / 2.23694
        anomalies = []
        for i in range(self.n):
            for j in range(self.n):
                if i == j:
                    continue
                dist = self.distances[i][j]
                dur = self.durations[i][j]
                if dist is None or dur is None or dist < 500:
                    continue
                implied = dist / expected_mps
                ratio = dur / max(implied, 1.0)
                if ratio >= ratio_threshold:
                    anomalies.append(MatrixAnomaly(
                        i, j, dur, round(implied, 1), round(ratio, 2),
                        "severe" if ratio >= 3.0 else "mild",
                    ))
        return anomalies

    def avg_outbound_duration(self, i: int) -> float:
        valid = [d for j, d in enumerate(self.durations[i]) if j != i and d is not None]
        return round(mean(valid), 1) if valid else 0.0


# ---------------------------------------------------------------------------
# Route corridor (geofence conformance)
# ---------------------------------------------------------------------------


class RouteCorridor:
    """Tests whether telemetry points stay within a corridor buffer (meters)
    around a polylined route."""

    def __init__(self, route: List[Tuple[float, float]], buffer_m: float = 200.0):
        if len(route) < 2:
            raise ValueError("route needs at least 2 points (lon, lat)")
        self.route = route          # (lon, lat) pairs
        self.buffer_m = buffer_m

    def distance_from_route(self, lat: float, lon: float) -> float:
        best = float("inf")
        for a, b in zip(self.route, self.route[1:]):
            d = cross_track_distance_m(lat, lon, a[1], a[0], b[1], b[0])
            if d < best:
                best = d
        return best

    def conforms(self, lat: float, lon: float) -> bool:
        return self.distance_from_route(lat, lon) <= self.buffer_m

    def conformance_ratio(self, points: List[TelemetryPoint]) -> float:
        ok = sum(1 for p in points if self.conforms(p.lat, p.lon))
        return round(ok / len(points), 4)


# ---------------------------------------------------------------------------
# Demo dataset generator (reproducible)
# ---------------------------------------------------------------------------


def make_synthetic_fleet(seed: int = 42) -> Dict[str, SpeedProfile]:
    """Generates synthetic telemetry for 5 vehicles around Harrisburg PA."""
    import random
    rng = random.Random(seed)
    # depot near Enola/Harrisburg
    depot_lat, depot_lon = 40.297, -76.885
    fleet = {}
    for vid in range(5):
        pts = []
        lat, lon = depot_lat + rng.uniform(-0.01, 0.01), depot_lon + rng.uniform(-0.01, 0.01)
        t = 1_794_000_000
        for _ in range(60):
            # mixed pattern: stationary or highway driving
            if rng.random() < 0.2:
                # dwell
                pass
            else:
                dlat = rng.uniform(-0.005, 0.008)  # ~300-900 m
                dlon = rng.uniform(-0.005, 0.008)
                lat += dlat
                lon += dlon
            t += 10
            pts.append(TelemetryPoint(round(lat, 5), round(lon, 5), t))
        fleet[f"veh_{vid}"] = SpeedProfile(pts)
    return fleet
