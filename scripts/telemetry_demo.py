#!/usr/bin/env python3
"""Fleet telemetry + Mapbox distance matrix demo."""

import json
from modules.telemetry import (
    MapboxClient,
    DistanceMatrixProcessor,
    RouteCorridor,
    make_synthetic_fleet,
)


def main():
    fleet = make_synthetic_fleet(seed=123)

    print("=== Fleet speed profiles (5 vehicles x 60 fixes) ===")
    for vid, sp in sorted(fleet.items()):
        s = sp.stats()
        print(f"  {vid:5s}  {s.mean_speed_mph:5.1f} mph avg | max {s.max_speed_mph:5.1f} | "
              f"dwell {s.dwell_ratio * 100:4.1f}% | speeding {s.speeding_ratio * 100:4.1f}%")

    # Mapbox matrix between fleet endpoints
    endpoints = [sp.points[-1] for sp in fleet.values()]
    coords = [(p.lon, p.lat) for p in endpoints]
    client = MapboxClient()
    proc = DistanceMatrixProcessor(client.matrix(coords), labels=list(fleet.keys()))

    print("\n=== Nearest-vehicle dispatch matrix (ETA) ===")
    for i, vid in enumerate(fleet.keys()):
        nearest = proc.nearest(i, k=2)
        etas = ", ".join(f"{name} ~{sec/60:.1f}m" for name, sec in nearest)
        print(f"  {vid:5s} -> {etas}")

    anomalies = proc.congestion_anomalies()
    print(f"\nCongestion anomalies flagged: {len(anomalies)}")

    route = [(sp.points[-1].lon, sp.points[-1].lat) for sp in fleet.values()]
    corridor = RouteCorridor(route[:3], buffer_m=500.0)
    ratio = corridor.conformance_ratio(fleet["veh_0"].points)
    print(f"veh_0 corridor conformance: {ratio * 100:.1f}%")

    gj = fleet["veh_0"].to_geojson()
    print(f"\nGeoJSON export: {len(gj['features'])} feature(s), "
          f"{gj['features'][0]['properties']['mean_speed_mph']:.1f} mph avg")


if __name__ == "__main__":
    main()
