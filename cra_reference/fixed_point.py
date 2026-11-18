"""Deterministic fixed-point execution for symbolic grid transformations.

The kernel deliberately does not generate programs. A caller supplies a
transformation and, optionally, a state validator. Candidate generation can
remain probabilistic; execution, validation, convergence detection, and
replay are deterministic at this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Iterable, Sequence

Grid = tuple[tuple[int, ...], ...]
Transform = Callable[[Grid], Sequence[Sequence[int]]]
Validator = Callable[[Grid], None]


class GridStateError(ValueError):
    """Raised when a grid is empty, ragged, or contains an illegal symbol."""


class NonConvergentError(RuntimeError):
    """Raised when a requested run does not reach a fixed point."""


def normalize_grid(grid: Sequence[Sequence[int]]) -> Grid:
    """Return a canonical immutable grid or raise ``GridStateError``."""
    if not grid:
        raise GridStateError("grid must contain at least one row")
    rows = tuple(tuple(row) for row in grid)
    width = len(rows[0])
    if width == 0:
        raise GridStateError("grid rows must contain at least one cell")
    if any(len(row) != width for row in rows):
        raise GridStateError("grid must be rectangular")
    if any(type(cell) is not int or cell < 0 or cell > 255 for row in rows for cell in row):
        raise GridStateError("grid cells must be integers in the range 0..255")
    return rows


def state_root(grid: Grid) -> str:
    """Hash dimensions and cells in a stable, unambiguous representation."""
    canonical = json.dumps(
        {"height": len(grid), "width": len(grid[0]), "cells": grid},
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class FixedPointResult:
    """Immutable execution trace for one transformation run."""

    initial: Grid
    final: Grid
    states: tuple[Grid, ...]
    state_roots: tuple[str, ...]
    converged: bool
    reason: str

    @property
    def iterations(self) -> int:
        return len(self.states) - 1


class FixedPointKernel:
    """Apply a deterministic grid transform until it reaches a fixed point."""

    def __init__(self, validator: Validator | None = None) -> None:
        self.validator = validator

    def run(
        self,
        initial: Sequence[Sequence[int]],
        transform: Transform,
        *,
        max_iterations: int = 64,
    ) -> FixedPointResult:
        if max_iterations < 0:
            raise ValueError("max_iterations must be non-negative")
        current = normalize_grid(initial)
        self._validate(current)
        states = [current]
        roots = [state_root(current)]
        seen = {current}

        for _ in range(max_iterations):
            candidate = normalize_grid(transform(current))
            self._validate(candidate)
            states.append(candidate)
            roots.append(state_root(candidate))
            if candidate == current:
                return FixedPointResult(
                    states[0],
                    candidate,
                    tuple(states),
                    tuple(roots),
                    True,
                    "fixed_point",
                )
            if candidate in seen:
                return FixedPointResult(
                    states[0],
                    candidate,
                    tuple(states),
                    tuple(roots),
                    False,
                    "cycle",
                )
            seen.add(candidate)
            current = candidate

        return FixedPointResult(
            states[0],
            current,
            tuple(states),
            tuple(roots),
            False,
            "max_iterations",
        )

    def require_fixed_point(
        self,
        initial: Sequence[Sequence[int]],
        transform: Transform,
        *,
        max_iterations: int = 64,
    ) -> FixedPointResult:
        """Run and raise if the transform does not reach a fixed point."""
        result = self.run(initial, transform, max_iterations=max_iterations)
        if not result.converged:
            raise NonConvergentError(
                f"transform did not converge: {result.reason}"
            )
        return result

    def replay(
        self,
        initial: Sequence[Sequence[int]],
        transform: Transform,
        expected_roots: Iterable[str],
        *,
        max_iterations: int = 64,
    ) -> FixedPointResult:
        """Re-run and require an identical state-root trace."""
        result = self.run(initial, transform, max_iterations=max_iterations)
        if tuple(expected_roots) != result.state_roots:
            raise NonConvergentError("replay produced a different state-root trace")
        return result

    def _validate(self, grid: Grid) -> None:
        if self.validator is not None:
            self.validator(grid)
