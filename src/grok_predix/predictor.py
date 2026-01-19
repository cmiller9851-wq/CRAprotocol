"""Wrapper around the Grok‑predix model for real‑time integrity forecasting."""

import numpy as np
from typing import Tuple
import joblib  # assuming the model is stored with joblib


def load_model(path: str):
    """Load a serialized scikit‑learn / XGBoost model."""
    return joblib.load(path)


class IntegrityForecaster:
    """
    Wrapper around the Grok‑predix model that outputs a breach‑probability.

    The forecaster accepts a feature vector derived from recent audit logs
    and returns a probability in the range 0‑1.  It also provides a simple
    confidence interval useful for automated rollback decisions.
    """

    def __init__(self, model_path: str):
        self.model = load_model(model_path)

    def predict(self, features: np.ndarray) -> Tuple[float, Tuple[float, float]]:
        """
        Return (probability, (lower_ci, upper_ci)).

        The CI is a placeholder 5 % window around the point estimate.
        """
        prob = self.model.predict_proba(features)[0, 1]
        ci = (max(0.0, prob - 0.05), min(1.0, prob + 0.05))
        return prob, ci
