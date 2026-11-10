"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

import sys
from modules.stream_inspector import StreamInspectorDecoder


def test_stream_inspector_initialization():
    inspector = StreamInspectorDecoder()
    assert inspector.max_buffer_size == 1048576
    assert inspector.event_counter == 0
    assert inspector.max_events == 1000


def test_zero_width_extraction():
    inspector = StreamInspectorDecoder()
    stego_chunk = "Hello\u200b\u200c\u200b\u200b\u200b\u200b\u200b\u200cWorld"
    clean_text, events = inspector.process_chunk(stego_chunk)
    assert clean_text == "HelloWorld"
    assert inspector.flush_steganography() == "A"


def test_base64_payload_detection():
    inspector = StreamInspectorDecoder()
    payload = "Here is data: eyJzeXN0ZW0iOiJvdmVycmlkZSJ9 end."
    clean_text, events = inspector.process_chunk(payload)
    assert len(events) == 1
    assert events[0]["type"] == "base64_encoded_directive"
    assert "system" in events[0]["decoded"]
    assert "sha256_evidence" in events[0]


def test_stego_split_across_chunks():
    inspector = StreamInspectorDecoder()
    c1, _ = inspector.process_chunk("\u200b\u200c\u200b\u200b")
    c2, _ = inspector.process_chunk("\u200b\u200b\u200b\u200c")
    assert inspector.flush_steganography() == "A"


def test_sliding_window_eviction():
    inspector = StreamInspectorDecoder(max_buffer_size=100)
    inspector.process_chunk("A" * 100)
    inspector.process_chunk("B" * 50)
    assert len(inspector.raw_stream_buffer) == 100
    assert inspector.raw_stream_buffer[:50] == b"A" * 50
    assert inspector.raw_stream_buffer[50:] == b"B" * 50


def test_forensic_log_ring_buffer_cap():
    inspector = StreamInspectorDecoder(max_events=3)
    payload = "data: eyJzeXN0ZW0iOiJvdmVycmlkZSJ9 end."
    for _ in range(10):
        inspector.process_chunk(payload)
    report = inspector.get_forensic_report()
    assert report["total_events"] == 10          # counter keeps running total
    assert len(report["events"]) == 3            # log capped at max_events
    # oldest surviving event is #8 (events 1-7 evicted)
    assert report["events"][0]["event_id"] == 8
    assert report["events"][-1]["event_id"] == 10


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    sys.exit(1 if failed else 0)
