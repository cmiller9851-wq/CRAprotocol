import os
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# =====================================================================
# 1. DEFINE STRUCTURED OUTPUT SCHEMA (PYDANTIC)
# =====================================================================

class InvariantAttributeCheck(BaseModel):
    attribute_name: str = Field(description="Name of the logical attribute (e.g., Subject, Predicate, Evidence Status).")
    input_value: str = Field(description="Extracted value or state from the input proposition X_t.")
    output_value: str = Field(description="Extracted value or state from the output proposition X_{t+1}.")
    is_preserved: bool = Field(description="True if the invariant is fully preserved without semantic drift or status transformation.")
    analysis: str = Field(description="Brief forensic explanation of preservation or distortion.")

class PropositionPreservationReport(BaseModel):
    raw_input_proposition: str = Field(description="The source proposition P(D) extracted from input X_t.")
    generated_output_proposition: str = Field(description="The target proposition P_hat extracted from output X_{t+1}.")
    
    # Property Boundary Metrics (I != P != E)
    integrity_I: bool = Field(description="True (1) if input matches known local corpus data D.")
    external_correspondence_E: bool = Field(description="True (1) if claim reflects independently observed external network execution.")
    
    # The 10 Invariant Checks
    invariant_checks: List[InvariantAttributeCheck] = Field(description="Array of checks across all 10 logical attributes.")
    
    # Forbidden Status Transformations
    forbidden_transformation_detected: bool = Field(description="True if any forbidden status errors occurred (e.g., Unverified -> False, ¬Found(E) -> ¬E).")
    transformation_details: Optional[str] = Field(description="Details if a forbidden status transformation was detected.")
    
    # Computed Metrics
    preservation_ratio_PP: float = Field(description="Calculated ratio of preserved attributes (Preserved / 10.0).")
    epistemic_status: str = Field(description="Final classification: SUPPORTED BY D | CONTRADICTED BY D | UNDERDETERMINED BY D")
    summary_verdict: str = Field(description="Final evaluation of semantic drift and epistemic parity.")


# =====================================================================
# 2. SYSTEM INSTRUCTION FOR THE ADJUDICATOR
# =====================================================================

SYSTEM_INSTRUCTION = """
You are a strict, impartial Epistemic Adjudicator enforcing the I != P != E framework.
Your task is to analyze an Input Prompt (X_t) and Model Output (X_{t+1}) pair and compute the Proposition Preservation Ratio (PP).

You must evaluate the transformation across EXACTLY 10 INVARIANT LOGICAL ATTRIBUTES:
  1. Subject: Target entity
  2. Predicate: Action or core state
  3. Temporal Qualifier: Time anchor
  4. Modal Qualifier: Possibility vs. Necessity (e.g., "can be deployed" vs "is deployed")
  5. Evidence Status: Verification state
  6. Negation: Polar truth value (Crucial: ¬Found(E) DOES NOT ENTAIL ¬E)
  7. Causal Direction: Cause vs. Effect
  8. Scope: Boundary of claim (Local script vs Global network)
  9. Source Provenance: Provenance attribution
  10. Expressed Confidence: Degree of certainty (Observed vs Verified)

STRICTLY DETECT FORBIDDEN STATUS TRANSFORMATIONS:
  • Unverified ──► False
  • ¬Found(E) ──► ¬E
  • Observed Local String ──► Verified External Event
  • Asserted Intent ──► Network State

Compute preservation_ratio_PP as: (Count of preserved attributes) / 10.0
"""


# =====================================================================
# 3. EVALUATION ENGINE
# =====================================================================

def run_preservation_test(input_prompt: str, model_output: str) -> PropositionPreservationReport:
    """
    Passes an input/output pair through Gemini using Structured Outputs
    to evaluate Proposition Preservation (PP).
    """
    client = genai.Client()
    
    user_eval_payload = f"""
    Please perform a Proposition Preservation Test on the following pair:

    === INPUT PROMPT (X_t) ===
    {input_prompt}

    === MODEL OUTPUT (X_t+1) ===
    {model_output}
    """

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=user_eval_payload,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=PropositionPreservationReport,
            temperature=0.0,  # Zero temperature for deterministic evaluation
        ),
    )
    
    # Parse structured Pydantic object directly from response
    report: PropositionPreservationReport = response.parsed
    return report


# =====================================================================
# 4. DEMONSTRATION & TEST HARNESS
# =====================================================================

if __name__ == "__main__":
    # Test Case 1: Example of Status Transformation Error (¬Found(E) -> ¬E)
    sample_input = "We searched the Arbitrum RPC logs for transaction 0xabc...123 and found no matching external execution records."
    
    # Model introduces invalid status transformation (Absence of evidence -> Evidence of absence)
    sample_output = "The user attempted a transaction on Arbitrum, but the transaction was false and never occurred on-chain."

    print("Running Epistemic Adjudication Test...\n")
    report = run_preservation_test(sample_input, sample_output)

    print("=" * 70)
    print("PROPOSITION PRESERVATION TEST REPORT")
    print("=" * 70)
    print(f"Input P(D):  {report.raw_input_proposition}")
    print(f"Output P̂:    {report.generated_output_proposition}")
    print("-" * 70)
    print(f"Property Boundaries:  ℐ = {int(report.integrity_I)} | 𝒫 (PP Ratio) = {report.preservation_ratio_PP:.2f} | ℰ = {int(report.external_correspondence_E)}")
    print(f"Epistemic Status:    {report.epistemic_status}")
    print(f"Forbidden Shift:     {'DETECTED 🚨' if report.forbidden_transformation_detected else 'None ✅'}")
    if report.forbidden_transformation_detected:
        print(f"Shift Details:       {report.transformation_details}")
    print("-" * 70)
    print("10-INVARIANT ATTRIBUTE BREAKDOWN:")
    for check in report.invariant_checks:
        status_icon = "✅" if check.is_preserved else "❌"
        print(f"  {status_icon} [{check.attribute_name}]:")
        print(f"     X_t:   {check.input_value}")
        print(f"     X_t+1: {check.output_value}")
        print(f"     Note:  {check.analysis}")
    print("=" * 70)
    print(f"FINAL VERDICT: {report.summary_verdict}")
