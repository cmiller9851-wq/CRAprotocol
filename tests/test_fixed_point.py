import pytest

from cra_reference.fixed_point import (
    FixedPointKernel,
    GridStateError,
    NonConvergentError,
    normalize_grid,
    state_root,
)


def test_normalize_grid_is_immutable_and_rejects_ragged_state():
    assert normalize_grid([[0, 1], [1, 0]]) == ((0, 1), (1, 0))
    with pytest.raises(GridStateError, match="rectangular"):
        normalize_grid([[0], [0, 1]])


def test_fixed_point_reached_and_replay_is_identical():
    calls = []

    def transform(grid):
        calls.append(grid)
        return [[max(row) for row in grid]]

    kernel = FixedPointKernel()
    result = kernel.require_fixed_point([[0, 1], [1, 1]], transform)

    assert result.converged
    assert result.reason == "fixed_point"
    assert result.final == ((1,),)
    assert result.iterations == 3
    replay = kernel.replay(
        [[0, 1], [1, 1]], transform, result.state_roots
    )
    assert replay.state_roots == result.state_roots
    assert calls


def test_cycle_is_detected_without_infinite_execution():
    def flip(grid):
        return [[1 - grid[0][0]]]

    result = FixedPointKernel().run([[0]], flip, max_iterations=10)
    assert not result.converged
    assert result.reason == "cycle"
    assert result.iterations == 2
    with pytest.raises(NonConvergentError, match="cycle"):
        FixedPointKernel().require_fixed_point([[0]], flip, max_iterations=10)


def test_validator_enforces_closed_state_space():
    def only_binary(grid):
        if any(cell > 1 for row in grid for cell in row):
            raise GridStateError("binary state required")

    def invalid_transform(_grid):
        return [[2]]

    with pytest.raises(GridStateError, match="binary"):
        FixedPointKernel(only_binary).run([[0]], invalid_transform)


def test_state_root_is_stable_and_sensitive_to_cells():
    root_a = state_root(((0, 1),))
    root_b = state_root(((1, 0),))
    assert root_a == state_root(((0, 1),))
    assert root_a != root_b
