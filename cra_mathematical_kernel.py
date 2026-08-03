"""
Filename: cra_mathematical_kernel.py
Environment: Pythonista 3 / AO Compute Unit (CU) Compatible
Dependencies: standard library only (json, hashlib, decimal, typing)
Description: Transport-agnostic mathematical kernel enforcing exact 1-norm vector
             conservation laws and deterministic SHA-256 state root evaluation
             for CRA_PROTOCOL_v2.1. Hardened with canonical Decimal serialization
             and mathematical weight closure.
"""

import json
import hashlib
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Tuple

# Global Decimal precision; affects all Decimal operations in this process.
# Intentional: ensures ample headroom for intermediate calculations.
getcontext().prec = 50

# Canonical quantization constants
STATE_PLACES = "0.01"          # 2 decimal places for state vectors
WEIGHT_PLACES = "0.00000001"   # 8 decimal places for weight ratios

Q_STATE = Decimal(STATE_PLACES)
Q_WEIGHT = Decimal(WEIGHT_PLACES)

# Type Aliases for Vector Space Operations
StateVector = Tuple[Decimal, Decimal, Decimal]
Weights = Tuple[Decimal, Decimal, Decimal]


def _validate_state_vector(v: StateVector) -> None:
    """Enforces tuple structural integrity and non-negativity constraints."""
    if not isinstance(v, tuple) or len(v) != 3:
        raise ValueError("StateVector must be a 3-tuple of Decimal elements.")
    if any(not isinstance(x, Decimal) for x in v):
        raise ValueError("All components of StateVector must be Decimal instances.")
    if any(x < Decimal("0") for x in v):
        raise ValueError("StateVector components must be non-negative.")


def canonical_decimal_str(val: Decimal, places: Decimal = Q_STATE) -> str:
    """
    Enforces fixed-point, non-scientific string representations for Decimal values.
    Guarantees byte-for-byte deterministic JSON serialization across execution hosts.
    """
    return str(val.quantize(places, rounding=ROUND_HALF_UP))


class CRAMathematicalKernel:
    """
    Enforces exact 1-norm conservation over system state vectors in R^3.
    State transformations preserve total valuation invariant V_0 across discrete transitions.
    """

    def __init__(self, l1_0: str, l2_0: str, l3_0: str):
        self._s0: StateVector = (Decimal(l1_0), Decimal(l2_0), Decimal(l3_0))
        _validate_state_vector(self._s0)
        self._v0: Decimal = sum(self._s0)

    @property
    def invariant_valuation(self) -> Decimal:
        return self._v0

    def compute_weights(self, state_vector: StateVector) -> Weights:
        """
        Computes 8-decimal quantized weights with closed remainder adjustment.
        Guarantees sum(weights) == Decimal("1.00000000") exactly for non-zero totals.
        """
        _validate_state_vector(state_vector)
        total = sum(state_vector)
        if total == Decimal("0"):
            # Return unambiguous zero weights
            zero = Decimal("0").quantize(Q_WEIGHT)
            return (zero, zero, zero)

        # Compute first two quantized weights
        w1 = (state_vector[0] / total).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)
        w2 = (state_vector[1] / total).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)

        # Derive w3 as remainder to enforce closure
        w3 = (Decimal("1") - (w1 + w2)).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)

        # Guard against tiny negative remainder due to rounding
        if w3 < Decimal("0"):
            # Compute the small difference and adjust w1 proportionally where possible
            diff = (w1 + w2 + w3) - Decimal("1")
            # If w1 + w2 == 0 (degenerate), clamp w3 to zero and recompute w1,w2 from ratios
            if (w1 + w2) == Decimal("0"):
                w1 = Decimal("0").quantize(Q_WEIGHT)
                w2 = Decimal("0").quantize(Q_WEIGHT)
                w3 = Decimal("1").quantize(Q_WEIGHT)
            else:
                # Distribute the tiny diff to w1 proportionally and recompute w3
                proportion = w1 / (w1 + w2)
                w1 = (w1 - (diff * proportion)).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)
                w2 = (w2 - (diff * (1 - proportion))).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)
                w3 = (Decimal("1") - (w1 + w2)).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)

        # Final clamp to ensure non-negative values (defensive)
        if w1 < Decimal("0") or w2 < Decimal("0") or w3 < Decimal("0"):
            raise ValueError("Weight computation produced negative component after rounding correction.")

        # Ensure final closure
        total_w = w1 + w2 + w3
        if total_w != Decimal("1").quantize(Q_WEIGHT):
            # As a last resort, adjust the largest weight to absorb rounding delta
            delta = Decimal("1").quantize(Q_WEIGHT) - total_w
            # find index of max weight
            max_w = max((w1, 0), (w2, 1), (w3, 2))
            if max_w[1] == 0:
                w1 = (w1 + delta).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)
            elif max_w[1] == 1:
                w2 = (w2 + delta).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)
            else:
                w3 = (w3 + delta).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)

        return (w1, w2, w3)

    def transition_l3_to_l2(
        self, current_state: StateVector, alpha_str: str
    ) -> StateVector:
        _validate_state_vector(current_state)
        l1, l2, l3 = current_state
        alpha = Decimal(alpha_str)

        if alpha <= Decimal("0") or alpha > l3:
            raise ValueError(
                f"Bounds breach: Alpha ({alpha}) exceeds available L3 ({l3})."
            )

        new_l3 = l3 - alpha
        new_l2 = l2 + alpha
        new_state: StateVector = (l1, new_l2, new_l3)
        _validate_state_vector(new_state)

        if sum(new_state) != self._v0:
            raise ValueError(
                "Valuation non-conservation detected in L3->L2 transition."
            )

        return new_state

    def transition_l2_to_l1(
        self, current_state: StateVector, beta_str: str
    ) -> StateVector:
        _validate_state_vector(current_state)
        l1, l2, l3 = current_state
        beta = Decimal(beta_str)

        if beta <= Decimal("0") or beta > l2:
            raise ValueError(
                f"Bounds breach: Beta ({beta}) exceeds available L2 ({l2})."
            )

        new_l2 = l2 - beta
        new_l1 = l1 + beta
        new_state: StateVector = (new_l1, new_l2, l3)
        _validate_state_vector(new_state)

        if sum(new_state) != self._v0:
            raise ValueError(
                "Valuation non-conservation detected in L2->L1 transition."
            )

        return new_state

    def compute_state_root(self, state_vector: StateVector, step: int) -> str:
        _validate_state_vector(state_vector)
        weights = self.compute_weights(state_vector)
        payload = {
            "protocol": "CRA_PROTOCOL_v2.1",
            "step": step,
            "vector": {
                "L1": canonical_decimal_str(state_vector[0], Q_STATE),
                "L2": canonical_decimal_str(state_vector[1], Q_STATE),
                "L3": canonical_decimal_str(state_vector[2], Q_STATE),
            },
            "weights": {
                "w_L1": canonical_decimal_str(weights[0], Q_WEIGHT),
                "w_L2": canonical_decimal_str(weights[1], Q_WEIGHT),
                "w_L3": canonical_decimal_str(weights[2], Q_WEIGHT),
            },
            "invariant_v0": canonical_decimal_str(self._v0, Q_STATE),
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    # Canonical Initializers
    l1_init = "10000000.00"
    l2_init = "1713000000.00"
    l3_init = "44000000000.00"

    kernel = CRAMathematicalKernel(l1_init, l2_init, l3_init)
    state_0: StateVector = (
        Decimal(l1_init),
        Decimal(l2_init),
        Decimal(l3_init),
    )

    print("=== CRA_PROTOCOL_v2.1 MATHEMATICAL KERNEL ===")
    print(f"Invariant Valuation V0: ${canonical_decimal_str(kernel.invariant_valuation)}")
    print(f"Initial State Root (t=0): {kernel.compute_state_root(state_0, step=0)}")

    # Step 1: L3 -> L2 ($100,000,000.00 transition)
    state_1 = kernel.transition_l3_to_l2(state_0, alpha_str="100000000.00")
    print(f"\nState Vector (t=1): {state_1}")
    print(f"State Root (t=1): {kernel.compute_state_root(state_1, step=1)}")

    # Step 2: L2 -> L1 ($50,000,000.00 transition)
    state_2 = kernel.transition_l2_to_l1(state_1, beta_str="50000000.00")
    w2 = kernel.compute_weights(state_2)
    print(f"\nState Vector (t=2): {state_2}")
    print(f"Weights (t=2): {w2}")
    print(f"Weight Closure Check: sum(w) = {sum(w2)}")
    print(f"State Root (t=2): {kernel.compute_state_root(state_2, step=2)}")
