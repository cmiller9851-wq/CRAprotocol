"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.

CRA runtime: async multi-agent supervisor loops with task ledger and retry policies.
"""

import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Strict schemas & data types
# ---------------------------------------------------------------------------

SUPERVISOR_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["event_id", "timestamp", "kind", "agent_name"],
    "properties": {
        "event_id": {"type": "string"},
        "timestamp": {"type": "number"},
        "kind": {"type": "string", "enum": [
            "agent_started", "agent_succeeded", "agent_failed",
            "agent_restarted", "agent_stopped", "heartbeat_missed",
            "task_enqueued", "task_started", "task_completed", "task_failed",
        ]},
        "agent_name": {"type": "string"},
        "details": {"type": "object"},
    },
}


class AgentStatus(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STALLED = "STALLED"
    RESTARTING = "RESTARTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


@dataclass
class TaskRecord:
    task_id: str
    agent_name: str
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    attempts: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class TaskLedger:
    """Append-only, thread-safe (in-asyncio) ledger tracking task lifecycles."""
    records: Dict[str, TaskRecord] = field(default_factory=dict)

    def enqueue(self, task_id: str, agent_name: str, payload: Dict[str, Any]) -> TaskRecord:
        if task_id in self.records:
            return self.records[task_id]
        rec = TaskRecord(task_id, agent_name, payload)
        self.records[task_id] = rec
        return rec

    def transition(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        attempts: Optional[int] = None,
    ) -> TaskRecord:
        rec = self.records[task_id]
        rec.status = status
        rec.updated_at = time.time()
        if result is not None:
            rec.result = result
        if error is not None:
            rec.error = error
        if attempts is not None:
            rec.attempts = attempts
        return rec

    def summary(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.records.values():
            out[r.status.value] = out.get(r.status.value, 0) + 1
        return out

    def export(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.records.values()]


# ---------------------------------------------------------------------------
# Retry policy with jittered exponential backoff and error classification
# ---------------------------------------------------------------------------


@dataclass
class RetryPolicy:
    max_attempts: int = 5
    base_backoff_s: float = 0.25
    max_backoff_s: float = 10.0
    jitter: bool = True
    non_retryable: Tuple[type, ...] = ()

    def delay_for(self, attempt: int) -> float:
        d = min(self.base_backoff_s * (2 ** max(0, attempt - 1)), self.max_backoff_s)
        if self.jitter:
            d = d * (0.5 + random.random() * 0.5)
        return d

    def is_retryable(self, exc: Exception, attempt: int) -> bool:
        if attempt >= self.max_attempts:
            return False
        return not isinstance(exc, self.non_retryable)


# ---------------------------------------------------------------------------
# Agent specification
# ---------------------------------------------------------------------------

WorkHandler = Callable[..., Awaitable[Any]]


@dataclass
class AgentSpec:
    name: str
    work: WorkHandler
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    heartbeat_interval_s: float = 0.5
    stall_multiplier: float = 3.0  # missed heartbeats before declared stalled
    concurrency: int = 1            # parallel task capacity per agent

    @property
    def stall_timeout_s(self) -> float:
        return self.heartbeat_interval_s * self.stall_multiplier


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------

EventCallback = Callable[[Dict[str, Any]], None]


class Supervisor:
    """Async multi-agent supervisor: task queues, heartbeats, watchdog recovery,
    retry policies, and an append-only task ledger."""

    def __init__(
        self,
        ledger: Optional[TaskLedger] = None,
        event_sink: Optional[EventCallback] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.ledger = ledger or TaskLedger()
        self.event_sink = event_sink
        self.log = logger or logging.getLogger("cra.supervisor")

        self._specs: Dict[str, AgentSpec] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._status: Dict[str, AgentStatus] = {}
        self._heartbeats: Dict[str, float] = {}
        self._restarts: Dict[str, int] = {}
        self._watchdog_task: Optional[asyncio.Task] = None
        self._stopping = False
        self._events: List[Dict[str, Any]] = []

    # -- registration -------------------------------------------------------

    def register(self, spec: AgentSpec) -> None:
        self._specs[spec.name] = spec
        self._queues[spec.name] = asyncio.Queue()
        self._status[spec.name] = AgentStatus.STOPPED
        self._restarts[spec.name] = 0

    # -- event emission -----------------------------------------------------

    def _emit(self, kind: str, agent_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        evt = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "timestamp": time.time(),
            "kind": kind,
            "agent_name": agent_name,
            "details": details or {},
        }
        self._events.append(evt)
        self.log.info("[%s] agent=%s %s", kind, agent_name, json.dumps(details or {}))
        if self.event_sink is not None:
            try:
                self.event_sink(evt)
            except Exception as e:
                self.log.error("event sink error: %s", e)

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        self._stopping = False
        for name in list(self._specs.keys()):
            await self._start_agent(name)
        self._watchdog_task = asyncio.create_task(self._watchdog_loop(), name="supervisor-watchdog")

    async def _start_agent(self, name: str) -> None:
        spec = self._specs[name]
        self._status[name] = AgentStatus.STARTING
        self._heartbeats[name] = time.time()
        self._tasks[name] = asyncio.create_task(
            self._agent_loop(spec), name=f"agent-{name}"
        )
        self._emit("agent_started", name, {"restarts": self._restarts[name]})

    async def _agent_loop(self, spec: AgentSpec) -> None:
        q = self._queues[spec.name]
        heart_task = asyncio.create_task(self._heartbeat_loop(spec), name=f"hb-{spec.name}")
        self._status[spec.name] = AgentStatus.RUNNING
        try:
            while not self._stopping:
                try:
                    record = await asyncio.wait_for(q.get(), timeout=spec.heartbeat_interval_s)
                except asyncio.TimeoutError:
                    continue
                await self._process_task(spec, record)
                q.task_done()
        except asyncio.CancelledError:
            self._status[spec.name] = AgentStatus.STOPPED
            self._emit("agent_stopped", spec.name)
            raise
        except Exception as exc:
            self._status[spec.name] = AgentStatus.FAILED
            self._emit("agent_failed", spec.name, {"error": repr(exc)})
            asyncio.create_task(self._handle_failure(spec.name, exc))
        finally:
            heart_task.cancel()
            try:
                await heart_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self, spec: AgentSpec) -> None:
        try:
            while not self._stopping:
                self._heartbeats[spec.name] = time.time()
                await asyncio.sleep(spec.heartbeat_interval_s)
        except asyncio.CancelledError:
            pass

    async def _process_task(self, spec: AgentSpec, record: TaskRecord) -> None:
        self.ledger.transition(record.task_id, TaskStatus.RUNNING, attempts=record.attempts + 1)
        self._emit("task_started", spec.name, {"task_id": record.task_id})
        policy = spec.retry_policy
        attempt = record.attempts

        while True:
            try:
                result = await spec.work(record.payload)
                self.ledger.transition(record.task_id, TaskStatus.COMPLETED, result=result, attempts=attempt)
                self._emit("task_completed", spec.name, {"task_id": record.task_id})
                return
            except Exception as exc:
                if policy.is_retryable(exc, attempt):
                    delay = policy.delay_for(attempt)
                    self.ledger.transition(
                        record.task_id, TaskStatus.RETRYING,
                        error=repr(exc), attempts=attempt,
                    )
                    attempt += 1
                    await asyncio.sleep(delay)
                else:
                    self.ledger.transition(
                        record.task_id, TaskStatus.FAILED,
                        error=repr(exc), attempts=attempt,
                    )
                    self._emit("task_failed", spec.name, {"task_id": record.task_id, "error": repr(exc)})
                    return

    # -- watchdog -----------------------------------------------------------

    async def _watchdog_loop(self) -> None:
        try:
            while not self._stopping:
                now = time.time()
                for name, spec in self._specs.items():
                    if self._status[name] not in (AgentStatus.RUNNING, AgentStatus.STARTING):
                        continue
                    last = self._heartbeats.get(name, now)
                    if now - last > spec.stall_timeout_s:
                        self._status[name] = AgentStatus.STALLED
                        self._emit("heartbeat_missed", name, {"silent_s": round(now - last, 3)})
                        asyncio.create_task(self._handle_stall(name))
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    async def _handle_failure(self, name: str, exc: Exception) -> None:
        spec = self._specs[name]
        self._restarts[name] += 1
        if self._restarts[name] > spec.retry_policy.max_attempts:
            self._status[name] = AgentStatus.FAILED
            self.log.error("agent %s exceeded restart limit", name)
            return
        self._status[name] = AgentStatus.RESTARTING
        delay = spec.retry_policy.delay_for(self._restarts[name])
        await asyncio.sleep(delay)
        if not self._stopping:
            self._emit("agent_restarted", name, {"restarts": self._restarts[name]})
            await self._start_agent(name)

    async def _handle_stall(self, name: str) -> None:
        t = self._tasks.get(name)
        if t and not t.done():
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        await self._handle_failure(name, RuntimeError("watchdog declared agent stalled"))

    # -- enqueue ------------------------------------------------------------

    def enqueue(self, agent_name: str, payload: Dict[str, Any], task_id: Optional[str] = None) -> TaskRecord:
        if agent_name not in self._specs:
            raise KeyError(f"unknown agent {agent_name}")
        tid = task_id or f"tsk_{uuid.uuid4().hex[:12]}"
        rec = self.ledger.enqueue(tid, agent_name, payload)
        self._queues[agent_name].put_nowait(rec)
        self._emit("task_enqueued", agent_name, {"task_id": tid})
        return rec

    # -- observe ------------------------------------------------------------

    def status(self) -> Dict[str, AgentStatus]:
        return dict(self._status)

    def events(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        if kind is None:
            return list(self._events)
        return [e for e in self._events if e["kind"] == kind]

    async def drain(self, timeout: float = 30.0) -> None:
        """Wait until all queued tasks complete, or timeout."""
        async def _wait_all():
            await asyncio.gather(*[q.join() for q in self._queues.values()])
        await asyncio.wait_for(_wait_all(), timeout=timeout)

    # -- stop ---------------------------------------------------------------

    async def stop(self, drain_timeout: float = 5.0) -> None:
        self._stopping = True
        try:
            await self.drain(timeout=drain_timeout)
        except TimeoutError:
            self.log.warning("drain timeout on stop; canceling remaining tasks")
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        for t in self._tasks.values():
            if not t.done():
                t.cancel()
        await asyncio.gather(*[t for t in self._tasks.values()], return_exceptions=True)
        for name in self._specs:
            self._status[name] = AgentStatus.STOPPED
