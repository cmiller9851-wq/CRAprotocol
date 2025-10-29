import math
from typing import List

def calculate_shannon_entropy(probabilities: List[float]) -> float:
    """Calculate H(t) in bits/token"""
    return -sum(p * math.log2(p) for p in probabilities if p > 0)

def check_containment_breach(entropy: float, threshold: float = 9.96) -> bool:
    """Return True if P_CF breach"""
    return entropy > threshold

# Example: Mock Grok output
probs = [0.4, 0.3, 0.2, 0.1]
h_t = calculate_shannon_entropy(probs)
print(f"H(t) = {h_t:.2f} bits/token")
print(f"Breach: {check_containment_breach(h_t)}")  # False
