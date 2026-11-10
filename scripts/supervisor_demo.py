#!/usr/bin/env python3
"""Runnable demo of the CRA multi-agent supervisor loops.

Shows:
1. Two worker agents processing queued tasks
2. Transient task errors retried and recovered
3. Agent crash auto-restarted up to the retry policy limit
4. Stalled heartbeat detected by the watchdog
5. Full task ledger summary and event audit trail
"""

import asyncio
import logging
import random
import time
from modules.supervisor import (
    Supervisor,
    AgentSpec,
    RetryPolicy,
    TaskStatus,
)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sup = Supervisor()

    policy = RetryPolicy(max_attempts=4, base_backoff_s=0.1, jitter=False)

    # Agent 1: data normalizer — sometimes transiently fails
    async def normalizer(payload):
        if random.random() < 0.25:
            raise RuntimeError("upstream rate limit")
        await asyncio.sleep(0.01)
        return {"normalized": payload["raw"].upper()}

    # Agent 2: auditor — stable worker
    async def auditor(payload):
        await asyncio.sleep(0.02)
        return {"audit_ok": len(payload.get("items", [])) > 0}

    sup.register(AgentSpec("normalizer", normalizer, policy, heartbeat_interval_s=0.2))
    sup.register(AgentSpec("auditor", auditor, policy, heartbeat_interval_s=0.2))

    await sup.start()
    print("Supervisor started. Enqueuing 20 tasks across 2 agents...")

    for i in range(10):
        sup.enqueue("normalizer", {"raw": f"chunk-{i}"})
        sup.enqueue("auditor", {"items": list(range(i + 1))})

    await sup.drain(timeout=10.0)

    # simulate a stalled heartbeat to show watchdog recovery
    print("\nSimulating missed heartbeat...")
    sup._heartbeats["auditor"] = time.time() - 10.0
    await asyncio.sleep(0.6)

    # simulate a crash-and-restart
    print("Simulating agent crash...")
    await sup._handle_failure("normalizer", RuntimeError("simulated crash"))
    await asyncio.sleep(0.4)
    sup.enqueue("normalizer", {"raw": "post-recovery-chunk"})
    await sup.drain(timeout=5.0)

    await sup.stop()

    print("\n--- Task Ledger Summary ---")
    for k, v in sup.ledger.summary().items():
        print(f"  {k}: {v}")

    print("\n--- Event audit trail (last 12) ---")
    for e in sup.events()[-12:]:
        print(f"  [{e['kind']:18s}] agent={e['agent_name']:10s} {e['details']}")

    print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(main())
