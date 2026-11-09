"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

import asyncio
import os
import time
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from modules.supervisor import (
    Supervisor,
    AgentSpec,
    RetryPolicy,
    AgentStatus,
)
from modules.telemetry import MapboxClient, DistanceMatrixProcessor, make_synthetic_fleet

app = FastAPI(title="CRA Supervisor & Telemetry Runtime", version="1.0.0")

_supervisor: Supervisor | None = None
_fleet = None


@app.on_event("startup")
async def startup():
    global _supervisor, _fleet
    _supervisor = Supervisor()
    policy = RetryPolicy(
        max_attempts=int(os.environ.get("RETRY_MAX_ATTEMPTS", "5")),
        base_backoff_s=float(os.environ.get("RETRY_BASE_BACKOFF", "0.25")),
        jitter=True,
    )
    hb = float(os.environ.get("HEARTBEAT_INTERVAL", "0.5"))

    async def telemetry_worker(payload):
        fleet = _fleet or make_synthetic_fleet(seed=7)
        sp = fleet.get(payload.get("vid", "veh_0"))
        return sp.stats().to_dict() if sp else None

    async def matrix_worker(payload):
        client = MapboxClient()
        coords = [tuple(c) for c in payload.get("coords", [])]
        mat = client.matrix(coords)
        return DistanceMatrixProcessor(mat).eta_matrix_minutes()

    _supervisor.register(AgentSpec("telemetry-worker", telemetry_worker, policy, heartbeat_interval_s=hb))
    _supervisor.register(AgentSpec("matrix-worker", matrix_worker, policy, heartbeat_interval_s=hb))
    await _supervisor.start()


@app.on_event("shutdown")
async def shutdown():
    if _supervisor:
        await _supervisor.stop(drain_timeout=1.0)


@app.get("/health")
async def health():
    if _supervisor is None:
        raise HTTPException(503, "not ready")
    st = _supervisor.status()
    ok = any(v in (AgentStatus.RUNNING, AgentStatus.STARTING) for v in st.values())
    return JSONResponse({"status": "healthy" if ok else "degraded", "agents": {k: v.value for k, v in st.items()}},
                        status_code=200 if ok else 503)


@app.post("/tasks/enqueue")
async def enqueue(body: Dict[str, Any]):
    agent = body.get("agent", "telemetry-worker")
    payload = body.get("payload", {})
    try:
        rec = _supervisor.enqueue(agent, payload)
    except KeyError as e:
        raise HTTPException(400, str(e))
    return rec.to_dict()


@app.get("/tasks")
async def list_tasks():
    return {"summary": _supervisor.ledger.summary(), "records": _supervisor.ledger.export()[-100:]}


@app.get("/events")
async def list_events(kind: str | None = None):
    return {"events": _supervisor.events(kind)[-200:]}


@app.post("/telemetry/matrix")
async def matrix(body: Dict[str, Any]):
    coords = [tuple(c) for c in body.get("coords", [])]
    client = MapboxClient()
    mat = client.matrix(coords)
    proc = DistanceMatrixProcessor(mat, labels=body.get("labels"))
    return {"etas_min": proc.eta_matrix_minutes(), "anomalies": len(proc.congestion_anomalies())}
