#!/usr/bin/env python3
"""Async load test against the CRA staging Kubernetes deployment.

Usage:
    # 1. port-forward the staging service locally:
    kubectl -n cra-staging port-forward svc/cra-supervisor-runtime 8000:80

    # 2. run the load test:
    python scripts/load_test_k8s.py --url http://127.0.0.1:8000 --concurrency 50 --duration 30
"""

import argparse
import asyncio
import statistics
import time
from typing import List
import httpx


async def worker(client: httpx.AsyncClient, url: str, end_time: float, latencies: List[float], errors: List[str]):
    import random
    rng = random.Random()
    coords = [(-76.920, 40.290), (-76.884, 40.264), (-77.009, 40.214),
              (-76.650, 40.285), (-77.195, 40.201)]
    while time.time() < end_time:
        t0 = time.perf_counter()
        try:
            if rng.random() < 0.6:
                # 60%: task enqueue -> supervisor
                r = await client.post(
                    f"{url}/tasks/enqueue",
                    json={"agent": rng.choice(["telemetry-worker", "matrix-worker"]),
                          "payload": {"vid": f"veh_{rng.randint(0,4)}", "coords": coords}},
                    timeout=10.0,
                    headers={"X402-Payment": "loadtest_demo_token"},
                )
            else:
                # 40%: direct telemetry matrix computation
                r = await client.post(
                    f"{url}/telemetry/matrix",
                    json={"coords": coords, "labels": ["A", "B", "C", "D", "E"]},
                    timeout=10.0,
                    headers={"X402-Payment": "loadtest_demo_token"},
                )
            if r.status_code == 200:
                latencies.append((time.perf_counter() - t0) * 1000.0)
            else:
                errors.append(f"HTTP {r.status_code}")
        except Exception as e:
            errors.append(repr(e)[:80])


async def run(url: str, concurrency: int, duration: float):
    print("=" * 72)
    print("      CRA SUPERVISOR RUNTIME — STAGING LOAD TEST")
    print("=" * 72)
    print(f"Target:        {url}")
    print(f"Concurrency:   {concurrency} virtual clients")
    print(f"Duration:      {duration:.0f} s\n")

    # health check first
    async with httpx.AsyncClient() as c:
        try:
            r = await c.get(f"{url}/health", timeout=10.0)
            print(f"Health:        HTTP {r.status_code} -> {r.text[:120]}")
        except Exception as e:
            print(f"Health:        UNREACHABLE ({e})")
            print("\nHint: if running outside the cluster, port-forward first:")
            print("  kubectl -n cra-staging port-forward svc/cra-supervisor-runtime 8000:80")
            return 1

    latencies: List[float] = []
    errors: List[str] = []

    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        end = time.time() + duration
        t0 = time.perf_counter()
        tasks = [asyncio.create_task(worker(client, url, end, latencies, errors)) for _ in range(concurrency)]
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - t0

    n = len(latencies)
    thru = n / elapsed if elapsed else 0
    lats = sorted(latencies)
    pct = lambda p: round(lats[int(len(lats) * p)], 1) if lats else 0.0

    print("\n--- Results ---")
    print(f"  Requests (2xx):    {n:,}")
    print(f"  Errors:            {len(errors):,}")
    print(f"  Throughput:        {thru:,.0f} req/s")
    if lats:
        print(f"  Latency p50:       {pct(0.50)} ms")
        print(f"  Latency p95:       {pct(0.95)} ms")
        print(f"  Latency p99:       {pct(0.99)} ms")
        print(f"  Latency mean:      {round(statistics.mean(lats), 1)} ms")
    if errors:
        sample = set(errors)
        print(f"  Error sample:      {list(sample)[:3]}")

    print("\n--- Assessment ---")
    if errors:
        print("  Status: DEGRADED under this load — check pod CPU/memory and HPA scaling.")
    else:
        print("  Status: STABLE — no errors observed at this concurrency.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--duration", type=float, default=30.0)
    args = ap.parse_args()
    return asyncio.run(run(args.url, args.concurrency, args.duration))


if __name__ == "__main__":
    raise SystemExit(main())
