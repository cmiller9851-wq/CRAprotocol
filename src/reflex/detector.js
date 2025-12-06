// Example: tighten drift‑score normalization
const normalizedScore = driftScore / 256;   // ensure value stays in 0‑1 range
if (normalizedScore > threshold) {
  // …existing breach handling…
}
