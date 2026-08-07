# live_cra_combined_runtime.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Dict, List, Tuple

getcontext().prec = 50

# -------------------- CRA Mathematical Kernel --------------------
Q01 = Decimal("0.01")                  # Balances quantization
QWEIGHT = Decimal("0.00000001")       # Weights quantization
ONE = Decimal("1.00000000")


def _q(x: Decimal, q: Decimal) -> Decimal:
    return x.quantize(q, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class KernelState:
    L1: Decimal
    L2: Decimal
    L3: Decimal
    weights: Tuple[Decimal, Decimal, Decimal, Decimal]

    @property
    def V0(self) -> Decimal:
        return self.L1 + self.L2 + self.L3


class CRAKernelInvariantError(ValueError):
    pass


class CRA_MathematicalKernel:
    def __init__(self, state: KernelState):
        s = self._normalize_state(state)
        self.state = s
        self.state_root = self._state_root(s)

    @staticmethod
    def _normalize_state(state: KernelState) -> KernelState:
        L1 = _q(state.L1, Q01)
        L2 = _q(state.L2, Q01)
        L3 = _q(state.L3, Q01)

        w0, w1, w2, w3 = state.weights
        ws = (
            _q(w0, QWEIGHT),
            _q(w1, QWEIGHT),
            _q(w2, QWEIGHT),
            _q(w3, QWEIGHT),
        )
        wclosed = CRA_MathematicalKernel._close_weights(ws)
        return KernelState(L1=L1, L2=L2, L3=L3, weights=wclosed)

    @staticmethod
    def _close_weights(
        weights: Tuple[Decimal, Decimal, Decimal, Decimal],
    ) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        w = list(weights)
        residual = ONE - sum(w)
        w[0] = _q(w[0] + _q(residual, QWEIGHT), QWEIGHT)

        if _q(sum(w), QWEIGHT) != ONE:
            raise CRAKernelInvariantError("Weight closure failed to reach exact sum=1.00000000")
        return (w[0], w[1], w[2], w[3])

    @staticmethod
    def _canonical_payload(s: KernelState) -> Dict[str, Any]:
        def dec_str(x: Decimal) -> str:
            return format(x, "f")

        return {
            "L1": dec_str(s.L1),
            "L2": dec_str(s.L2),
            "L3": dec_str(s.L3),
            "weights": {
                "w0": dec_str(s.weights[0]),
                "w1": dec_str(s.weights[1]),
                "w2": dec_str(s.weights[2]),
                "w3": dec_str(s.weights[3]),
            },
            "V0": dec_str(s.V0),
        }

    def _state_root(self, s: KernelState) -> str:
        payload = self._canonical_payload(s)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def transition(self, *, move_amount: Decimal, L_from: str, L_to: str) -> Tuple[KernelState, str]:
        if L_from not in ("L1", "L2", "L3") or L_to not in ("L1", "L2", "L3") or L_from == L_to:
            raise CRAKernelInvariantError("Invalid tier conversion")

        amt = _q(move_amount, Q01)
        if not amt.is_finite() or amt < 0:
            raise CRAKernelInvariantError("Invalid transition amount")

        old = self.state
        oldV0 = old.V0

        cur = {"L1": old.L1, "L2": old.L2, "L3": old.L3}
        cur[L_from] = _q(cur[L_from] - amt, Q01)
        cur[L_to] = _q(cur[L_to] + amt, Q01)

        new_state = KernelState(
            L1=cur["L1"],
            L2=cur["L2"],
            L3=cur["L3"],
            weights=old.weights,
        )

        if new_state.L1 < 0 or new_state.L2 < 0 or new_state.L3 < 0:
            raise CRAKernelInvariantError("Bounds breach: negative balance")

        if new_state.V0 != oldV0:
            raise CRAKernelInvariantError("Invariant breach: valuation drift")

        self.state = new_state
        self.state_root = self._state_root(new_state)
        return self.state, self.state_root


# -------------------- Global Attribution Protocol --------------------
@dataclass
class CreatorLedger:
    author_id: str
    name: str
    ip_assets: List[str] = field(default_factory=list)
    cumulative_compensation_usd: float = 0.0


class GlobalAttributionProtocol:
    def __init__(self):
        self.registry: Dict[str, CreatorLedger] = {}
        self.global_telemetry_log: List[Dict[str, Any]] = []

    def register_creator(self, author_id: str, name: str) -> None:
        if author_id not in self.registry:
            self.registry[author_id] = CreatorLedger(author_id=author_id, name=name)
            print(f"[CRAprotocol] Registered sovereign creator: {name} (ID: {author_id})")

    def register_asset(self, author_id: str, asset_signature: str) -> None:
        if author_id in self.registry:
            self.registry[author_id].ip_assets.append(asset_signature)
            print(f"[CRAprotocol] Asset '{asset_signature}' bound to creator {author_id}.")

    def process_compute_ingestion(
        self,
        consumer_id: str,
        asset_signature: str,
        compute_units_used: float,
        micro_royalty_rate_per_unit: float,
    ) -> None:
        target_creator = None
        for creator in self.registry.values():
            if asset_signature in creator.ip_assets:
                target_creator = creator
                break

        if target_creator:
            compensation = compute_units_used * micro_royalty_rate_per_unit
            target_creator.cumulative_compensation_usd += compensation

            event_record = {
                "status": "CONTAINMENT_VERIFIED",
                "consumer": consumer_id,
                "asset": asset_signature,
                "author": target_creator.name,
                "compensation_issued_usd": compensation,
                "clearance": "779AX-DETERMINISTIC",
            }
            self.global_telemetry_log.append(event_record)
            print(f"[COMPLIANCE] Attribution verified for {target_creator.name}. Micro-compensation issued: ${compensation:.6f}")
        else:
            print(f"[BREACH_TRACE] Unregistered asset signature detected: {asset_signature}. Triggering containment protocol.")

    def generate_global_audit_ledger(self) -> str:
        ledger_summary = {
            "total_registered_creators": len(self.registry),
            "total_events_logged": len(self.global_telemetry_log),
            "creators": {
                cid: {"name": c.name, "total_earned": c.cumulative_compensation_usd}
                for cid, c in self.registry.items()
            },
        }
        return json.dumps(ledger_summary, indent=4)


# -------------------- One live runtime script --------------------
def main() -> None:
    asset_signature = "CRAprotocol-Core-Specification-v1"
    consumer_id = "AI-Runtime-Cluster-Alpha"

    compute_units_used = 15420.0
    micro_royalty_rate_per_unit = 0.00005

    move_amount = Decimal("25.50")
    L_from = "L3"
    L_to = "L1"

    grid = GlobalAttributionProtocol()
    grid.register_creator(author_id="CREATOR-001", name="Cory Michael Miller")
    grid.register_asset(author_id="CREATOR-001", asset_signature=asset_signature)

    grid.process_compute_ingestion(
        consumer_id=consumer_id,
        asset_signature=asset_signature,
        compute_units_used=compute_units_used,
        micro_royalty_rate_per_unit=micro_royalty_rate_per_unit,
    )

    print("\n--- GLOBAL LEDGER STATE ---")
    print(grid.generate_global_audit_ledger())

    init_state = KernelState(
        L1=Decimal("150.50"),
        L2=Decimal("45.25"),
        L3=Decimal("304.25"),
        weights=(Decimal("0.25"), Decimal("0.25"), Decimal("0.25"), Decimal("0.25")),
    )

    kernel = CRA_MathematicalKernel(init_state)

    print(f"\nInitial State Root: {kernel.state_root}")
    print(f"Initial Balances -> L1: {kernel.state.L1}, L2: {kernel.state.L2}, L3: {kernel.state.L3}, V0: {kernel.state.V0}")

    kernel.transition(move_amount=move_amount, L_from=L_from, L_to=L_to)

    print(f"\nPost-Transition State Root: {kernel.state_root}")
    print(f"Updated Balances -> L1: {kernel.state.L1}, L2: {kernel.state.L2}, L3: {kernel.state.L3}, V0: {kernel.state.V0}")


if __name__ == "__main__":
    main()
