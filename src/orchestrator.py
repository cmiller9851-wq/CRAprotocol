import os
import sys
import time
import queue
import threading
import hashlib

class AtomicBarrier:
    """Thread-safe circuit breaker to handle zero-leak graceful shutdowns."""
    def __init__(self):
        self._lock = threading.Lock()
        self._tripped = False

    def trip(self):
        with self._lock:
            self._tripped = True

    @property
    def is_tripped(self):
        with self._lock:
            return self._tripped

def simulate_worker(core_id: str, task_queue: queue.PriorityQueue, barrier: AtomicBarrier):
    """
    Simulates an isolated virtual core running a strict priority queue execution loop.
    Enforces process isolation principles mapped to NIST SP 800-53 SC-39.
    """
    while not barrier.is_tripped:
        try:
            # Non-blocking pull to prevent worker hanging during shutdown
            priority, task_id, latency_sim = task_queue.get(timeout=0.1)
            
            start_time = time.perf_counter()
            time.sleep(latency_sim / 1000.0) # Simulate payload processing drift
            execution_time = (time.perf_counter() - start_time) * 1000.0
            
            # Direct raw write to stdout to avoid standard print lock bottlenecks
            sys.stdout.write(
                f"[{core_id}][{task_id}] Executed task (Priority: {priority}) in {execution_time:.4f}ms\n"
            )
            sys.stdout.flush()
            task_queue.task_done()
        except queue.Empty:
            continue

def initialize_fabric():
    """Spuns up the virtual multi-core matrix and floods it with workloads."""
    cores = 6
    barrier = AtomicBarrier()
    core_threads = []
    core_queues = {}

    sys.stdout.write(f"[ORCHESTRATOR] Allocating computational paths across {cores} virtual processing cores...\n")
    
    # Spawn thread isolated queues
    for i in range(cores):
        core_id = f"CORE_{i:02d}"
        core_queues[core_id] = queue.PriorityQueue()
        t = threading.Thread(target=simulate_worker, args=(core_id, core_queues[core_id], barrier))
        t.start()
        core_threads.append((core_id, t))
        
    sys.stdout.write("[ORCHESTRATOR] Fabric initialization complete. Systems active.\n\n")
    sys.stdout.write("[PIPELINE] Injecting asynchronous workloads into system routing queues...\n")
    sys.stdout.flush()

    # Define tasks with explicit priorities (Priority 1 = Fast Math, Priority 5 = Slow Network)
    tasks = [
        (1, "MATH_BLK_00", 0.8), (1, "MATH_BLK_01", 0.8), (1, "MATH_BLK_02", 0.8),
        (1, "MATH_BLK_03", 0.8), (1, "MATH_BLK_04", 0.8), (1, "MATH_BLK_05", 0.8),
        (1, "MATH_BLK_06", 0.8), (1, "MATH_BLK_07", 0.8), (1, "MATH_BLK_08", 0.8),
        (1, "MATH_BLK_09", 0.8), (1, "MATH_BLK_10", 0.8), (1, "MATH_BLK_11", 0.8),
        (5, "NET_REG_00", 2.5),  (5, "NET_REG_01", 7.0),  (5, "NET_REG_02", 8.8),
        (5, "NET_REG_03", 5.3),  (5, "NET_REG_04", 2.5),  (5, "NET_REG_05", 3.5),
        (5, "NET_REG_06", 2.5),  (5, "NET_REG_07", 2.5),  (5, "NET_REG_08", 2.4),
        (5, "NET_REG_09", 2.4),  (5, "NET_REG_10", 2.4),  (5, "NET_REG_11", 2.5)
    ]

    # Deterministic Context Hashing to preserve L1/L2 cache locality
    for priority, task_id, latency in tasks:
        context_hash = sum(ord(char) for char in task_id)
        assigned_core_numeric = context_hash % cores
        target_core_id = f"CORE_{assigned_core_numeric:02d}"
        core_queues[target_core_id].put((priority, task_id, latency))

    # Allow processing window to execute completely
    time.sleep(0.5)

    sys.stdout.write("\n[ORCHESTRATOR] Initiating graceful tearing down of execution fabric...\n")
    barrier.trip()

    for core_id, thread in core_threads:
        thread.join()
        sys.stdout.write(f"[{core_id}] Operational loop gracefully shutdown.\n")
        
    sys.stdout.write("[ORCHESTRATOR] Compute fabric completely dark.\n")
    sys.stdout.flush()

if __name__ == "__main__":
    initialize_fabric()
