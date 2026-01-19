# CRA Protocol – Integration Guide

This guide explains how to integrate the CRA (Computational‑Law‑Resilience‑Act) protocol
into AI systems so they meet both the CRA standards and the EU Cyber Resilience Act
requirements. It covers the core components, deployment steps, and the new
cross‑jurisdiction audit workflow.

---

## 1. Core components

| Component | Purpose | Key API |
|-----------|---------|---------|
| **Merkle tree** (`src/chain_of_custody/merkle.py`) | Immutable audit‑log chaining; provides cryptographic proof of data integrity. | `MerkleTree.generate_proof`, `MerkleTree.verify_proof` |
| **DQFR calculator** (`src/dqfr/metrics.py`) | Computes the Data Quality Fidelity Ratio – a normalized measure of data‑quality drift. | `compute_dqfr` |
| **Integrity forecaster** (`src/grok_predix/predictor.py`) | Real‑time breach‑probability prediction based on recent audit logs. | `IntegrityForecaster.predict` |
| **Example script** (`examples/run_audit.py`) | Demonstrates end‑to‑end usage of the three components. | `main(model_id)` |

---

## 2. Deployment checklist

1. **Add the CRA package** to your environment  

   ```bash
   pip install -r requirements.txt   # includes pandas, numpy, joblib, etc.
