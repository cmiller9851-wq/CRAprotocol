#!/usr/bin/env python3
"""End-to-end integration: Mapbox congestion anomalies drive the CRA
async multi-agent supervisor loops for automated rerouting & dispatch."""

import asyncio
import copy
import logging
import random
import time
from typing import Dict, List, Tuple
from modules.telemetry import (
    MapboxClient,
    DistanceMatrixProcessor,
    MatrixAnomaly,
    RouteCorridor,
    make_synthetic_fleet,
)
from modules.supervisor import (
    Supervisor,
    AgentSpec,
    RetryPolicy,
    TaskStatus,
)


def inject_severe_congestion(matrix: Dict, i: int, j: int, multiplier: float = 3.5) -> Dict:
    """Simulates a severe bottleneck (e.g., bridge closure, accident) on OD pair (i, j)."""
    m = copy.deepcopy(matrix)
    m["durations"][i][j] = round(m["durations"][i][j] * multiplier, 1)
    m["durations"][j][i] = round(m["durations"][j][i] * (multiplier * 0.8), 1)  # asymmetric
    return m


async def main():
    logging.basicConfig(level=logging.WARNING)

    # ------------------------------------------------------------------ 1. Fleet & baseline matrix
    fleet = make_synthetic_fleet(seed=123)
    labels = list(fleet.keys())
    coords = [(sp.points[-1].lon, sp.points[-1].lat) for sp in fleet.values()]
    client = MapboxClient()
    base_matrix = client.matrix(coords)
    baseline = DistanceMatrixProcessor(base_matrix, labels=labels)

    # ------------------------------------------------------------------ 2. Inject severe congestion
    # bottleneck between veh_0 and veh_4 (e.g., Susquehanna River crossing incident)
    congested_matrix = inject_severe_congestion(base_matrix, 0, 4, multiplier=3.5)
    congested = DistanceMatrixProcessor(congested_matrix, labels=labels)
    anomalies = congested.congestion_anomalies(ratio_threshold=1.75)

    print("=" * 72)
    print("   CONGESTION ANOMALY DETECTED -> MULTI-AGENT SUPERVISOR ACTIVATED")
    print("=" * 72)
    print(f"\nBaseline veh_0 -> veh_4: {base_matrix['durations'][0][4]/60:.1f} min")
    print(f"Congested veh_0 -> veh_4: {congested_matrix['durations'][0][4]/60:.1f} min "
          f"({congested_matrix['durations'][0][4]/base_matrix['durations'][0][4]:.1f}x slower)")
    print(f"Anomalies flagged: {len(anomalies)} "
          f"({sum(1 for a in anomalies if a.severity == 'severe')} severe)\n")

    # ------------------------------------------------------------------ 3. Supervisor + agents
    sup = Supervisor()
    policy = RetryPolicy(max_attempts=4, base_backoff_s=0.02, jitter=False)
    rng = random.Random(42)

    # Agent 1: incident triage — validates anomaly severity, sometimes transiently fails
    async def anomaly_triage(payload):
        if rng.random() < 0.25:
            raise RuntimeError("traffic-data feed timeout")
        a = payload["anomaly"]
        ratio = a["actual_duration_s"] / max(a["implied_duration_s"], 1)
        return {"pair": f"{labels[a['i']]}-{labels[a['j']]}", "ratio": round(ratio, 2), "action": "reroute_required"}

    # Agent 2: detour planner — validates alternate route conformance
    async def detour_planner(payload):
        orig_sp = fleet[labels[payload["from_idx"]]]
        dest_sp = fleet[labels[payload["to_idx"]]]
        route = [(orig_sp.points[-1].lon, orig_sp.points[-1].lat),
                 (dest_sp.points[-1].lon, dest_sp.points[-1].lat)]
        corridor = RouteCorridor(route, buffer_m=1200.0)  # detour corridor
        conf = corridor.conformance_ratio(dest_sp.points[-10:])
        return {"alternate_conf": conf, "reroute": "DETOUR_NORTH"}

    # Agent 3: dispatch advisor — recomputes nearest-vehicle pairing on degraded matrix
    async def dispatch_advisor(payload):
        proc = DistanceMatrixProcessor(payload["matrix"], labels=labels)
        return {labels[i]: [f"{n} ~{sec/60:.1f}m" for n, sec in proc.nearest(i, k=2)]
                for i in range(proc.n)}

    sup.register(AgentSpec("triage", anomaly_triage, policy, heartbeat_interval_s=0.2))
    sup.register(AgentSpec("planner", detour_planner, policy, heartbeat_interval_s=0.2))
    sup.register(AgentSpec("advisor", dispatch_advisor, policy, heartbeat_interval_s=0.2))

    await sup.start()

    # Enqueue work for each detected anomaly
    for a in anomalies:
        d = {"i": a.i, "j": a.j, "actual_duration_s": a.actual_duration_s,
             "implied_duration_s": a.implied_duration_s, "severity": a.severity}
        sup.enqueue("triage", {"anomaly": d})
        sup.enqueue("planner", {"from_idx": a.i, "to_idx": a.j})
    sup.enqueue("advisor", {"matrix": congested_matrix})

    await sup.drain(timeout=10.0)
    await sup.stop()

    # ------------------------------------------------------------------ 4. Results
    print("--- Task Ledger ---")
    for k, v in sup.ledger.summary().items():
        print(f"  {k}: {v}")

    print("\n--- Agent outputs ---")
    for r in sup.ledger.records.values():
        if r.agent_name == "triage":
            print(f"  [TRIAGE ] {r.result}")
        elif r.agent_name == "planner":
            print(f"  [PLANNER] {r.result}")
        elif r.agent_name == "advisor":
            print("  [ADVISOR] updated dispatch recommendations:")
            for vid, pairs in r.result.items():
                print(f"            {vid:5s} -> {', '.join(pairs)}")

    kinds = {}
    for e in sup.events():
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print("\n--- Event audit trail ---")
    for k, v in kinds.items():
        print(f"  {k:20s}: {v}")

    restarts = sup.events("agent_restarted")
    print(f"\nCrash-and-restart events during simulation: {len(restarts)}")

    print("\n" + "=" * 72)
    print("  SIMULATION COMPLETE — ANOMALY DETECTED, TRIAGED, REROUTED, LEDGERED")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
