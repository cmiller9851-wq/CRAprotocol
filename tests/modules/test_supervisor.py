"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""
import asyncio
import time
import pytest

from modules.supervisor.core import (
    Supervisor,
    AgentSpec,
    AgentStatus,
    TaskStatus,
    TaskLedger,
    RetryPolicy,
    SUPERVISOR_EVENT_SCHEMA,
)

FAST_POLICY = RetryPolicy(max_attempts=3, base_backoff_s=0.01, max_backoff_s=0.05, jitter=False)


@pytest.mark.asyncio
async def test_supervisor_start_and_stop():
    sup = Supervisor()
    done = []

    async def worker(payload):
        done.append(payload)

    sup.register(AgentSpec("echo", worker, FAST_POLICY, heartbeat_interval_s=0.05))
    await sup.start()
    await asyncio.sleep(0.02)
    assert sup.status()["echo"] == AgentStatus.RUNNING
    await sup.stop()
    assert sup.status()["echo"] == AgentStatus.STOPPED


@pytest.mark.asyncio
async def test_task_happy_path():
    sup = Supervisor()

    async def worker(payload):
        return payload["x"] * 2

    sup.register(AgentSpec("double", worker, FAST_POLICY, heartbeat_interval_s=0.05))
    await sup.start()
    rec = sup.enqueue("double", {"x": 21})
    await sup.drain(timeout=2.0)
    await sup.stop()
    summary = sup.ledger.summary()
    assert summary.get("COMPLETED") == 1
    assert sup.ledger.records[rec.task_id].result == 42
    assert sup.ledger.records[rec.task_id].status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_task_retries_transient_error():
    sup = Supervisor()
    calls = {"n": 0}

    async def worker(payload):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    sup.register(AgentSpec("retry-worker", worker, FAST_POLICY, heartbeat_interval_s=0.05))
    await sup.start()
    sup.enqueue("retry-worker", {})
    await sup.drain(timeout=2.0)
    await sup.stop()
    summary = sup.ledger.summary()
    assert summary.get("COMPLETED") == 1
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_task_fails_after_max_attempts():
    sup = Supervisor()

    async def worker(payload):
        raise RuntimeError("permanent")

    sup.register(AgentSpec("failing", worker, RetryPolicy(max_attempts=2, base_backoff_s=0.01, jitter=False), heartbeat_interval_s=0.05))
    await sup.start()
    sup.enqueue("failing", {})
    await sup.drain(timeout=2.0)
    await sup.stop()
    assert sup.ledger.summary().get("FAILED") == 1


@pytest.mark.asyncio
async def test_non_retryable_error_fails_fast():
    class PoisonError(Exception):
        pass

    policy = RetryPolicy(max_attempts=5, base_backoff_s=0.01, jitter=False, non_retryable=(PoisonError,))
    sup = Supervisor()

    async def worker(payload):
        raise PoisonError("bad data")

    sup.register(AgentSpec("fast-fail", worker, policy, heartbeat_interval_s=0.05))
    await sup.start()
    sup.enqueue("fast-fail", {})
    await sup.drain(timeout=2.0)
    await sup.stop()
    rec = list(sup.ledger.records.values())[0]
    assert rec.status == TaskStatus.FAILED
    assert rec.attempts == 1  # no retry


def test_retry_backoff_growth():
    p = RetryPolicy(max_attempts=5, base_backoff_s=0.5, max_backoff_s=4.0, jitter=False)
    delays = [p.delay_for(a) for a in range(1, 6)]
    assert delays == [0.5, 1.0, 2.0, 4.0, 4.0]


def test_ledger_idempotency_and_summary():
    ledger = TaskLedger()
    r1 = ledger.enqueue("t1", "ag", {"n": 1})
    r2 = ledger.enqueue("t1", "ag", {"n": 99})
    assert r1.payload["n"] == 1 and r1 is r2
    assert ledger.summary() == {"PENDING": 1}
    assert len(ledger.export()) == 1


@pytest.mark.asyncio
async def test_agent_crash_auto_restarted():
    sup = Supervisor()

    async def worker(payload):
        return "recovered"

    sup.register(AgentSpec("flaky", worker, FAST_POLICY, heartbeat_interval_s=0.05))
    await sup.start()
    # inject an unhandled harness exception to simulate a real agent crash
    await sup._handle_failure("flaky", RuntimeError("simulated crash"))
    await asyncio.sleep(0.1)
    sup.enqueue("flaky", {"a": 2})
    await sup.drain(timeout=3.0)
    await sup.stop()
    assert sup._restarts["flaky"] >= 1
    assert sup.ledger.summary().get("COMPLETED", 0) >= 1
    kinds = [e["kind"] for e in sup.events()]
    assert "agent_restarted" in kinds


@pytest.mark.asyncio
async def test_watchdog_recovers_stalled_agent():
    sup = Supervisor()
    stalled = {"done": False}

    async def worker(payload):
        # stall: block heartbeat loop by not yielding via sleep but spinning
        stalled["done"] = True
        return "ok"

    spec = AgentSpec("staller", worker, FAST_POLICY, heartbeat_interval_s=0.05, stall_multiplier=2.0)
    sup.register(spec)
    await sup.start()
    # force heartbeat staleness
    sup._heartbeats["staller"] = time.time() - 10.0
    await asyncio.sleep(0.25)
    await sup.stop()
    kinds = [e["kind"] for e in sup.events()]
    assert "heartbeat_missed" in kinds


@pytest.mark.asyncio
async def test_parallel_agents():
    sup = Supervisor()

    async def slow_work(payload):
        await asyncio.sleep(0.05)
        return payload["v"]

    for name in ("alpha", "beta", "gamma"):
        sup.register(AgentSpec(name, slow_work, FAST_POLICY, heartbeat_interval_s=0.05))
    await sup.start()
    t0 = time.time()
    for name in ("alpha", "beta", "gamma"):
        sup.enqueue(name, {"v": name})
    await sup.drain(timeout=2.0)
    elapsed = time.time() - t0
    await sup.stop()
    assert sup.ledger.summary().get("COMPLETED") == 3
    # 3x 50ms in parallel should finish well under 3x serial (150ms)
    assert elapsed < 0.2


@pytest.mark.asyncio
async def test_event_schema_conformance():
    sup = Supervisor()

    async def noop(payload):
        return None

    sup.register(AgentSpec("noop", noop, FAST_POLICY, heartbeat_interval_s=0.05))
    await sup.start()
    sup.enqueue("noop", {})
    await sup.drain(timeout=2.0)
    await sup.stop()
    valid_kinds = set(SUPERVISOR_EVENT_SCHEMA["properties"]["kind"]["enum"])
    for e in sup.events():
        for req in SUPERVISOR_EVENT_SCHEMA["required"]:
            assert req in e
        assert e["kind"] in valid_kinds


def test_enqueue_unknown_agent_raises():
    sup = Supervisor()
    with pytest.raises(KeyError):
        sup.enqueue("ghost", {})
