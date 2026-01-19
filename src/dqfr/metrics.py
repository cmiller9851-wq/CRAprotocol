"""DQFR (Data Quality Fidelity Ratio) calculation utilities."""

from typing import List
from dataclasses import dataclass


@dataclass
class AuditEntry:
    """Minimal representation of a forensic log entry."""
    timestamp: int
    quality_score: float  # Expected range 0‑100


def compute_dqfr(log_entries: List[AuditEntry]) -> float:
    """
    Calculate the Data Quality Fidelity Ratio (DQFR).

    DQFR = (Σ quality_score) / (len(log_entries) × max_score)

    Returns a percentage in the range 0‑100.  An empty log yields 0.0.
    """
    if not log_entries:
        return 0.0
    total = sum(e.quality_score for e in log_entries)
    max_score = 100.0
    return (total / (len(log_entries) * max_score)) * 100
