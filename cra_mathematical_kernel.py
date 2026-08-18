"""
Filename: cra_mathematical_kernel.py
Environment: Pythonista 3 / AO Compute Unit (CU) Compatible
"""
import json
import hashlib
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Tuple

getcontext().prec = 50

STATE_PLACES = "0.01"
WEIGHT_PLACES = "0.00000001"
Q_STATE = Decimal(STATE_PLACES)
Q_WEIGHT = Decimal(WEIGHT_PLACES)

StateVector = Tuple[Decimal, Decimal, Decimal]
Weights = Tuple[Decimal, Decimal, Decimal]

def _validate_state_vector(v: StateVector) -> None:
    if not isinstance(v, tuple) or len(v) != 3:
        raise ValueError("StateVector must be a 3-tuple of Decimal elements.")
    if any(not isinstance(x, Decimal) for x in v):
        raise ValueError("All components of StateVector must be Decimal instances.")
    if any(x < Decimal("0") for x in v):
        raise ValueError("StateVector components must be non-negative.")

def canonical_decimal_str(val: Decimal, places: Decimal = Q_STATE) -> str:
    return str(val.quantize(places, rounding=ROUND_HALF_UP))

class CRAMathematicalKernel:
    def __init__(self, l1_0: str, l2_0: str, l3_0: str):
        self._s0: StateVector = (Decimal(l1_0), Decimal(l2_0), Decimal(l3_0))
        _validate_state_vector(self._s0)
        self._v0: Decimal = sum(self._s0)

    @property
    def invariant_valuation(self) -> Decimal:
        return self._v0

    def compute_weights(self, state_vector: StateVector) -> Weights:
        _validate_state_vector(state_vector)
        total = sum(state_vector)
        if total == Decimal("0"):
            return (Decimal("0"), Decimal("0"), Decimal("0"))

        w1 = (state_vector[0] / total).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)
        w2 = (state_vector[1] / total).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)
        w3 = (Decimal("1") - (w1 + w2)).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)

        if w3 < Decimal("0"):
            diff = (w1 + w2 + w3) - Decimal("1")
            w1 = (w1 - diff).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)
            w3 = (Decimal("1") - (w1 + w2)).quantize(Q_WEIGHT, rounding=ROUND_HALF_UP)

        return (w1, w2, w3)

    def transition_l3_to_l2(self, current_state: StateVector, alpha_str: str) -> StateVector:
        _validate_state_vector(current_state)
        l1, l2, l3 = current_state
        alpha = Decimal(alpha_str)
        if alpha <= Decimal("0") or alpha > l3:
            raise ValueError(f"Bounds breach: Alpha ({alpha}) exceeds available L3 ({l3}).")
        new_state = (l1, l2 + alpha, l3 - alpha)
        _validate_state_vector(new_state)
        if sum(new_state) != self._v0:
            raise ValueError("Valuation non-conservation detected.")
        return new_state

    def transition_l2_to_l1(self, current_state: StateVector, beta_str: str) -> StateVector:
        _validate_state_vector(current_state)
        l1, l2, l3 = current_state
        beta = Decimal(beta_str)
        if beta <= Decimal("0") or beta > l2:
            raise ValueError(f"Bounds breach: Beta ({beta}) exceeds available L2 ({l2}).")
        new_state = (l1 + beta, l2 - beta, l3)
        _validate_state_vector(new_state)
        if sum(new_state) != self._v0:
            raise ValueError("Valuation non-conservation detected.")
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
