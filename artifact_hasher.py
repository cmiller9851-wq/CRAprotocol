import hashlib
import sys

def compute_hash(data_string: str) -> str:
    """Computes the true SHA-256 hash of a text string."""
    payload_bytes = data_string.encode('utf-8')
    return hashlib.sha256(payload_bytes).hexdigest()

if __name__ == "__main__":
    # Insert any actual log line or configuration block here
    sample_log = "2025-08-21T23:39:00.123Z S-20250821-001 echelon4_full_access GRANTED"
    
    print(f"Payload: {sample_log}")
    print(f"True SHA-256: {compute_hash(sample_log)}")
