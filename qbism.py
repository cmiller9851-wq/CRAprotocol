import numpy as np

class QBistBitEngine:

    def __init__(self, initial_p=None):
        # Default to Maximally Mixed State (Uniform Prior: p_i = 1/4)
        if initial_p is None:
            self.p = np.array([0.25, 0.25, 0.25, 0.25], dtype=np.float64)
        else:
            self.p = np.array(initial_p, dtype=np.float64)
            self._validate_coherence()

    def _validate_coherence(self):
        # Enforce valid quantum probability boundary: Sum(p_i^2) <= 1/2 for d=2
        assert np.isclose(np.sum(self.p), 1.0), "Probabilities must sum to 1."
        p_sq_sum = np.sum(self.p**2)
        assert p_sq_sum <= 0.5 + 1e-9, f"Non-physical state: Sum(p_i^2) = {p_sq_sum} > 0.5"

    def predict_outcome(self, conditional_matrix_q):
        """
        Ur-Born Rule Evaluation: P(F_j) = 3 * sum_i(p_i * q_{j|i}) - 1
        """
        # conditional_matrix_q shape: (n_outcomes, 4)
        P_F = 3.0 * np.dot(conditional_matrix_q, self.p) - 1.0
        return P_F

    def update_experience(self, outcome_k: int):
        """
        Executes QBist belief update upon experiencing outcome k (0-indexed).
        """
        pk = self.p[outcome_k]
        p_prime = np.full(4, 1.0 / 3.0, dtype=np.float64)
        p_prime[outcome_k] = 1.0 / 3.0 + (2.0 / 3.0) * ((3.0 * pk - 1.0) / (2.0 * pk))
        self.p = p_prime
        return self.p

# Verification Execution
engine = QBistBitEngine(initial_p=[0.25, 0.25, 0.25, 0.25])
updated_p = engine.update_experience(outcome_k=0)
print("Updated QBist Probability Vector:", updated_p)
