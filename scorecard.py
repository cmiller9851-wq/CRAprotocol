# =========================================================================
# CRA PROTOCOL PROPRIETARY NOTICE (LICENSE EXCEPTION)
# COPYRIGHT (C) QUICKPROMPT SOLUTIONS™ / CORY MILLER. ALL RIGHTS RESERVED.
# 
# WARNING: The constants and formulas within this file—specifically the
# H(t) entropy threshold (9.96 bits/token) and the P_CF scoring function—
# are EXCLUDED from the repository's Apache 2.0 license. These elements
# are proprietary Intellectual Property and are the subject of pending
# USPTO Utility Patent claims.
# 
# Use of these proprietary claims for commercial purposes, revenue generation,
# or litigation requires a separate, executed Enterprise Licensing Agreement (ELA) 
# with QuickPrompt Solutions™.
# =========================================================================
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
