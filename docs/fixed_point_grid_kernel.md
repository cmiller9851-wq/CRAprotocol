# Fixed-point grid kernel

`cra_reference.fixed_point.FixedPointKernel` implements the closed transformation relation:

```text
s_(alpha + 1) = T(s_alpha)
lim(alpha -> infinity) T(s_alpha) = s*
```

The kernel treats a grid as an immutable rectangular tuple of integer cells. It validates every state, applies a caller-supplied transformation, records a SHA-256 root for every state, and stops when the next state equals the current state.

```python
from cra_reference import FixedPointKernel


def stabilize(grid):
    # Example only: collapse each row to its maximum, then stabilize.
    return [[max(row) for row in grid]]

result = FixedPointKernel().require_fixed_point([[0, 1], [1, 1]], stabilize)
assert result.final == ((1,),)
assert result.state_roots
```

A validator can enforce a closed state space. For example, a binary-grid validator can reject any candidate containing a symbol outside `{0, 1}`. A malformed or ragged grid is rejected before or after transformation.

The kernel detects cycles and iteration exhaustion instead of treating either as convergence. `require_fixed_point()` raises `NonConvergentError` for those cases. `replay()` reruns the transform and requires the exact same state-root trace, making nondeterministic candidate executors observable at the execution boundary.

The module does not claim to discover ARC-AGI rules or to prove semantic correctness. Candidate generation may happen elsewhere. This module provides the deterministic execution, closure, convergence, and replay boundary after a candidate transformation has been supplied.
