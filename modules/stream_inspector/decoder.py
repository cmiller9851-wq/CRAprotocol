"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

"""Optimized streaming inspector: zero-width steganography extraction,
base64 directive detection, and bounded sliding-window forensics."""

import base64
import hashlib
import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple


class OptimizedStreamInspectorDecoder:
    """Ultra-optimized, low-latency streaming inspector engineered for
    high-throughput production environments with minimal memory allocation."""

    __slots__ = (
        "max_buffer_size",
        "max_events",
        "active_bits",
        "stego_buffer",
        "raw_stream_buffer",
        "event_counter",
        "forensic_log",
        "_b64_compiled_regex",
    )

    def __init__(self, max_buffer_size: int = 1048576, max_events: int = 1000):
        self.max_buffer_size = max_buffer_size
        self.max_events = max_events
        self.active_bits: List[str] = []
        self.stego_buffer: List[str] = []
        self.raw_stream_buffer = bytearray()
        self.event_counter = 0
        self.forensic_log = deque(maxlen=max_events)
        self._b64_compiled_regex = re.compile(rb"[A-Za-z0-9+/]{20,}={0,2}")

    def process_chunk(self, chunk: str) -> Tuple[str, List[Dict[str, Any]]]:
        clean_chars = []
        stego_buf = self.stego_buffer
        active_bits = self.active_bits

        for char in chunk:
            if char == "\u200b":
                active_bits.append("0")
            elif char == "\u200c":
                active_bits.append("1")
            else:
                clean_chars.append(char)
                continue

            if len(active_bits) >= 8:
                byte_str = "".join(active_bits[:8])
                del active_bits[:8]
                try:
                    stego_buf.append(chr(int(byte_str, 2)))
                except ValueError:
                    pass

        cleaned_text = "".join(clean_chars)
        chunk_bytes = cleaned_text.encode("utf-8", errors="ignore")

        buffer_len = len(self.raw_stream_buffer)
        incoming_len = len(chunk_bytes)
        if buffer_len + incoming_len > self.max_buffer_size:
            overflow = (buffer_len + incoming_len) - self.max_buffer_size
            del self.raw_stream_buffer[:overflow]
        self.raw_stream_buffer.extend(chunk_bytes)

        events: List[Dict[str, Any]] = []
        matches = self._b64_compiled_regex.findall(chunk_bytes)
        for match in matches:
            try:
                padding = 4 - (len(match) % 4)
                padded = match + (b"=" * padding if padding < 4 else b"")
                decoded_bytes = base64.b64decode(padded, validate=True)
                decoded_str = decoded_bytes.decode("utf-8", errors="strict")

                lower = decoded_bytes.lower()
                if b"{" in decoded_bytes or b"system" in lower or b"override" in lower:
                    self.event_counter += 1
                    raw_str = match.decode("utf-8", errors="ignore")
                    event = {
                        "event_id": self.event_counter,
                        "type": "base64_encoded_directive",
                        "raw_match": raw_str,
                        "decoded": decoded_str,
                        "decoded_value": decoded_str,
                        "sha256_evidence": hashlib.sha256(match).hexdigest(),
                    }
                    events.append(event)
                    self.forensic_log.append(event)
            except Exception:
                continue

        return cleaned_text, events

    def flush_steganography(self) -> Optional[str]:
        if not self.stego_buffer:
            return None
        result = "".join(self.stego_buffer)
        self.stego_buffer.clear()
        return result

    def get_forensic_report(self) -> Dict[str, Any]:
        stream_bytes = bytes(self.raw_stream_buffer)
        return {
            "total_events": self.event_counter,
            "stream_sha256": hashlib.sha256(stream_bytes).hexdigest(),
            "events": list(self.forensic_log),
        }
