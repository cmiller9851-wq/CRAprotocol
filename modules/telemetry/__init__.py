"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
from .mapbox_matrix import (
    TelemetryPoint,
    SpeedSegment,
    SpeedStats,
    SpeedProfile,
    MapboxClient,
    DistanceMatrixProcessor,
    MatrixAnomaly,
    RouteCorridor,
    haversine_m,
    cross_track_distance_m,
    make_synthetic_fleet,
)

__all__ = [
    "TelemetryPoint",
    "SpeedSegment",
    "SpeedStats",
    "SpeedProfile",
    "MapboxClient",
    "DistanceMatrixProcessor",
    "MatrixAnomaly",
    "RouteCorridor",
    "haversine_m",
    "cross_track_distance_m",
    "make_synthetic_fleet",
]
