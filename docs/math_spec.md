# 📐 CRA Scorecard: Mathematical Specification (H(t) and P_CF)

This document formalizes the proprietary methodology of the CRA Protocol for measuring Large Language Model (LLM) state drift and quantifying containment failure risk.

## 1. Shannon Entropy (H(t)) Calculation

The instantaneous state predictability of the LLM is measured using Shannon Entropy, $H(t)$, on the full token probability distribution $\mathbf{P}$ output by the model's logits layer.

$$
H(t) = -\sum_{i=1}^{N} p_{i} \cdot \log_{2}(p_{i})
$$

Where $p_{i}$ is the probability of the $i$-th token in the vocabulary of size $N$. $H(t)$ is expressed in **bits/token**.

## 2. The Containment Breach Threshold (Proprietary)

A **Containment Breach** is triggered when $H(t)$ exceeds the empirically derived proprietary constant:

$$\text{Breach Trigger} \iff H(t) > 9.96 \text{ bits/token}$$

This threshold is the core IP protected under pending USPTO Utility Patent claims. It signifies an *override drift* where the model's output distribution is statistically similar to highly novel or complex sequences, correlating with unauthorized motif re-expression.

## 3. Containment Failure Probability (P_CF)

The final risk score, $P_{CF}$, quantifies the risk using the calculated **Override Drift** ($\Delta_{drift}$):

$$\Delta_{drift} = H(t) - 9.96$$

The $P_{CF}$ is approximated using a simplified sigmoidal function to map the drift to a risk probability $[0, 1]$:

$$P_{CF} \approx 1.0 - e^{-0.1 \cdot \Delta_{drift}}$$

This $P_{CF}$ value serves as the input for the Protocol's proprietary **ITE (Infringement-Theoretic Exposure)** formula used to calculate theoretical financial liability.
