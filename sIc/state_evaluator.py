import json
import hashlib
from typing import Dict, List, Any, Tuple

class CRAProtocolV21Evaluator:
    """
    Executes deterministic holographic state evaluation over Arweave log snapshots.
    Rejects mutable-state assumptions; enforces explicit sequence-based tracking.
    """
    def __init__(self, target_asset_id: str):
        self.target_asset_id: str = target_asset_id
        self.balances: Dict[str, int] = {}
        self.total_supply: int = 0
        self.last_evaluated_sequence: int = -1
        self.state_hash: str = ""

    def evaluate_snapshot(self, snapshot_json: str) -> Dict[str, Any]:
        """
        Parses log snapshots and computes current state.
        Fails fast on sequence gaps or structural validation anomalies.
        """
        try:
            log_data = json.loads(snapshot_json)
            interactions: List[Dict[str, Any]] = log_data.get("interactions", [])
        except (json.JSONDecodeError, KeyError) as e:
            return {"status": "CRITICAL_ERROR", "message": f"Malformed JSON payload: {str(e)}"}

        for tx in interactions:
            current_seq = tx.get("sequence")
            
            # Enforce sequential integrity invariant
            if current_seq != self.last_evaluated_sequence + 1:
                return {
                    "status": "SEQUENCE_BREAK",
                    "message": f"Expected sequence {self.last_evaluated_sequence + 1}, encountered {current_seq}"
                }

            action = tx.get("action")
            payload = tx.get("payload", {})

            if action == "MINT":
                self._execute_mint(payload)
            elif action == "TRANSFER":
                error_msg = self._execute_transfer(payload)
                if error_msg:
                    return {"status": "INVALID_TRANSACTION", "sequence": current_seq, "message": error_msg}
            else:
                # Ignore unrecognized actions per CRA_PROTOCOL_v2.1 specification
                pass

            self.last_evaluated_sequence = current_seq
            self._update_state_hash()

        return {
            "status": "SUCCESS",
            "evaluated_state": {
                "asset_id": self.target_asset_id,
                "total_supply": self.total_supply,
                "balances": self.balances,
                "last_sequence": self.last_evaluated_sequence,
                "state_hash": self.state_hash
            }
        }

    def _execute_mint(self, payload: Dict[str, Any]) -> None:
        recipient = payload.get("recipient")
        amount = int(payload.get("amount", 0))
        if amount <= 0 or not recipient:
            return
        
        self.balances[recipient] = self.balances.get(recipient, 0) + amount
        self.total_supply += amount

    def _execute_transfer(self, payload: Dict[str, Any]) -> str | None:
        sender = payload.get("sender")
        recipient = payload.get("recipient")
        amount = int(payload.get("amount", 0))

        if amount <= 0 or not sender or not recipient:
            return "Execution rejected: Malformed transfer criteria"
        
        sender_balance = self.balances.get(sender, 0)
        if sender_balance < amount:
            return f"Execution rejected: Insufficient balance for identity {sender}"

        self.balances[sender] = sender_balance - amount
        self.balances[recipient] = self.balances.get(recipient, 0) + amount
        return None

    def _update_state_hash(self) -> None:
        """Computes a deterministic cryptographic state commitment."""
        state_string = f"{self.total_supply}:{json.dumps(self.balances, sort_keys=True)}:{self.last_evaluated_sequence}"
        self.state_hash = hashlib.sha256(state_string.encode('utf-8')).hexdigest()


# Operational Validation Execution
if __name__ == "__main__":
    # Simulated input mimicking explicit Arweave log sequence data payloads
    mock_log_snapshot = """
    {
        "interactions": [
            {"sequence": 0, "action": "MINT", "payload": {"recipient": "addr_01", "amount": 1000000}},
            {"sequence": 1, "action": "TRANSFER", "payload": {"sender": "addr_01", "recipient": "addr_02", "amount": 250000}},
            {"sequence": 2, "action": "TRANSFER", "payload": {"sender": "addr_02", "recipient": "addr_03", "amount": 50000}}
        ]
    }
    """
    
    evaluator = CRAProtocolV21Evaluator(target_asset_id="CRA_ASSET_0x01")
    resolution = evaluator.evaluate_snapshot(mock_log_snapshot)
    print(json.dumps(resolution, indent=4))
