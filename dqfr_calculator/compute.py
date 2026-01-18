# dqfr_calculator/compute.py
import pandas as pd

def dqfr_score(df: pd.DataFrame, quality_rules: dict) -> float:
    """
    df: dataset to evaluate
    quality_rules: {"missing_rate":0.02, "bias_threshold":0.05, ...}
    Returns a ratio between 0 and 1.
    """
    total = len(df)
    passed = total

    # Example rule: missing values
    if "missing_rate" in quality_rules:
        miss = df.isnull().mean().max()
        if miss > quality_rules["missing_rate"]:
            passed -= total * (miss - quality_rules["missing_rate"])

    # Example rule: simple bias check on a binary label
    if "bias_threshold" in quality_rules and "label" in df.columns:
        pos_rate = df["label"].mean()
        if abs(pos_rate - 0.5) > quality_rules["bias_threshold"]:
            passed -= total * 0.1  # penalize 10 %

    return max(passed / total, 0.0)
