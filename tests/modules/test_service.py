"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
import pytest
import httpx
from modules.supervisor.service import app, startup, shutdown, gateway


@pytest.mark.asyncio
async def test_service_health_and_endpoints():
    await startup()
    pay_hdr = {"X402-Payment": "test_pass_through"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # 1. free endpoints
        r = await c.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

        # 2. unpaid protected endpoint -> 402 challenge
        r = await c.post("/tasks/enqueue", json={"agent": "telemetry-worker", "payload": {"vid": "veh_0"}})
        assert r.status_code == 402
        assert r.headers.get("X402-Required") == "true"
        body = r.json()
        assert body["protocol"] == "x402"
        assert body["amount"] == gateway.default_price

        # 3. paid call succeeds + settlement header attached
        r = await c.post("/tasks/enqueue", json={"agent": "telemetry-worker", "payload": {"vid": "veh_0"}},
                         headers=pay_hdr)
        assert r.status_code == 200
        assert "task_id" in r.json()
        assert r.headers.get("X402-Settlement-Status") == "CONFIRMED"

        # 4. unknown agent -> 400
        r = await c.post("/tasks/enqueue", json={"agent": "no-such-agent", "payload": {}}, headers=pay_hdr)
        assert r.status_code == 400

        # 5. tasks list (free read)
        r = await c.get("/tasks")
        assert "summary" in r.json()

        # 6. paid telemetry matrix
        coords = [(-76.920, 40.290), (-76.884, 40.264), (-77.009, 40.214)]
        r = await c.post("/telemetry/matrix", json={"coords": coords, "labels": ["A", "B", "C"]}, headers=pay_hdr)
        assert r.status_code == 200
        assert len(r.json()["etas_min"]) == 3

        # 7. events list
        r = await c.get("/events")
        assert len(r.json()["events"]) >= 1

        # 8. revenue summary records the settlements
        r = await c.get("/revenue")
        assert r.status_code == 200
        rev = r.json()
        assert rev["settlements_count"] >= 3
        assert rev["total_revenue_usdc"] > 0

    await shutdown()
