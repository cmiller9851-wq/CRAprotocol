"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
import pytest
import httpx
from modules.supervisor.service import app, startup, shutdown


@pytest.mark.asyncio
async def test_service_health_and_endpoints():
    await startup()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

        r = await c.post("/tasks/enqueue", json={"agent": "telemetry-worker", "payload": {"vid": "veh_0"}})
        assert r.status_code == 200
        assert "task_id" in r.json()

        r = await c.post("/tasks/enqueue", json={"agent": "no-such-agent", "payload": {}})
        assert r.status_code == 400

        r = await c.get("/tasks")
        assert "summary" in r.json()

        coords = [(-76.920, 40.290), (-76.884, 40.264), (-77.009, 40.214)]
        r = await c.post("/telemetry/matrix", json={"coords": coords, "labels": ["A", "B", "C"]})
        assert r.status_code == 200
        assert len(r.json()["etas_min"]) == 3

        r = await c.get("/events")
        assert len(r.json()["events"]) >= 1

    await shutdown()
