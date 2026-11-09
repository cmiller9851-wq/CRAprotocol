"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

import time
from modules.stream_inspector import StreamInspectorDecoder


def run_benchmark():
    inspector = StreamInspectorDecoder()
    payload_chunk = (
        "Normal text streaming chunk with some data "
        "eyJzeXN0ZW0iOiJvdmVycmlkZSJ9 \u200c\u200b\u200b\u200b\u200b\u200b\u200b\u200c\n"
    )
    iterations = 100000

    start_time = time.perf_counter()
    for _ in range(iterations):
        inspector.process_chunk(payload_chunk)
    duration = time.perf_counter() - start_time

    print(f"Processed {iterations} chunks in {duration:.4f} seconds.")
    print(f"Throughput: {iterations / duration:.2f} chunks/sec.")
    print(f"Forensic Report: {inspector.get_forensic_report()['total_events']} events logged.")


if __name__ == "__main__":
    run_benchmark()
