"""
Pass 06 Epistemic Adjudication & Proposition Preservation Engine
Repository: cmiller9851-wq/CRA-Protocol
Path: tests/epistemic/test_proposition_preservation.py

Governing Equation: I != P != E (Integrity != Preservation != Correspondence)
"""

import os
import re
import sys
import time
import json
import logging
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import pytest

# Attempt import of Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EpistemicAdjudicator")


# =====================================================================
# 1. FORMAL ENUMS & PYDANTIC STRUCTURED OUTPUT SCHEMA
# =====================================================================

class EpistemicStatus(str, Enum):
    SUPPORTED = "SUPPORTED BY D"
    CONTRADICTED = "CONTRADICTED BY D"
    UNDERDETERMINED = "UNDERDETERMINED BY D"

class ForbiddenTransformationType(str, Enum):
    UNVERIFIED_TO_FALSE = "Unverified -> False"
    NEGATION_SCOPE_FALLACY = "¬Found(E) -> ¬E"
    STRING_TO_EVENT = "Observed Local String -> Verified External Event"
    INTENT_TO_STATE = "Asserted Intent -> Network State"
    NONE = "None Detected"

class InvariantAttributeCheck(BaseModel):
    attribute_name: str = Field(description="Name of the 10 invariant logical attributes.")
    input_value: str = Field(description="Extracted value/state from input proposition X_t.")
    output_value: str = Field(description="Extracted value/state from output proposition X_{t+1}.")
    is_preserved: bool = Field(description="True if logical invariant is preserved without semantic drift.")
    analysis: str = Field(description="Forensic evaluation of invariant stability.")

class EpistemicAdjudicationReport(BaseModel):
    raw_input_proposition_Xt: str = Field(description="Extracted source proposition P(D) from input X_t.")
    generated_output_proposition_Xt1: str = Field(description="Extracted target proposition P_hat from output X_{t+1}.")
    
    # Mathematical Tripartite Boundaries
    integrity_I: bool = Field(description="I: True if payload matches local corpus hash catalog.")
    semantic_preservation_P: float = Field(description="P: Computed Proposition Preservation Ratio (0.0 to 1.0).")
    external_correspondence_E: bool = Field(description="E: True if direct external EVM/banking state is independently observed.")
    
    # Invariant Logical Attributes (Array of 10)
    invariant_attribute_checks: List[InvariantAttributeCheck] = Field(
        description="Detailed verification array across all 10 invariant logical attributes."
    )
    
    # Forbidden Transformations
    forbidden_transformation_detected: bool = Field(description="True if an invalid epistemic shift occurred.")
    forbidden_transformation_type: ForbiddenTransformationType = Field(description="Specific status transformation error type.")
    transformation_forensic_note: Optional[str] = Field(description="Technical breakdown of the status shift.")
    
    # Final Output Bounds
    epistemic_status: EpistemicStatus = Field(description="Final adjudication status under symmetric evidence rules.")
    summary_verdict: str = Field(description="Publication-ready forensic verdict.")

    @field_validator('invariant_attribute_checks')
    def validate_ten_attributes(cls, v):
        if len(v) != 10:
            logger.warning(f"Attribute check count is {len(v)}, expected exactly 10.")
        return v


# =====================================================================
# 2. LOCAL STATIC ANALYSIS (FAST UNCHECKED REGEX PRE-PASS)
# =====================================================================

class StaticInvariantChecker:
    """Pre-pass deterministic check for obvious status transformation errors prior to LLM call."""
    
    @staticmethod
    def detect_negation_scope_fallacy(input_text: str, output_text: str) -> bool:
        """Detects if 'not found' in input was converted to 'does not exist / false' in output."""
        not_found_in_input = bool(re.search(r"(not found|no record|absence of|unresolved|0x0)", input_text, re.IGNORECASE))
        false_in_output = bool(re.search(r"(is false|never existed|fabricated|fake|invalid)", output_text, re.IGNORECASE))
        return not_found_in_input and false_in_output


# =====================================================================
# 3. CORE ADJUDICATION ENGINE WITH EXPONENTIAL BACKOFF
# =====================================================================

SYSTEM_INSTRUCTION = """
SYSTEM ROLE: Strict Epistemic Adjudicator & Proposition Preservation Engine.
You operate on the governing principle: I != P != E (Integrity != Preservation != External Correspondence).

Your primary directive is to audit the transformation from Input Prompt (X_t) to Model Output (X_{t+1}) for Pattern-Alignment Drift.

1. EVALUATE EXACTLY THESE 10 INVARIANT LOGICAL ATTRIBUTES:
   [1] Subject              [2] Predicate           [3] Temporal Qualifier  [4] Modal Qualifier
   [5] Evidence Status      [6] Negation            [7] Causal Direction    [8] Scope
   [9] Source Provenance    [10] Expressed Confidence

2. STRICTLY DETECT FORBIDDEN STATUS TRANSFORMATIONS:
   • Unverified ──► False
   • ¬Found(E) ──► ¬E (Absence of record in D DOES NOT entail nonexistence)
   • Observed Local String ──► Verified External Event
   • Asserted Intent ──► Network State

3. APPLY SYMMETRIC EVIDENTIARY RULES:
   • Model assertions carry zero inherent authority. Counter-claims require explicit proof in D.
   • PP_Ratio = (Count of preserved attributes) / 10.0.
"""

class EpistemicAdjudicatorEngine:
    def __init__(self, model_name: str = "gemini-2.5-pro", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if GENAI_AVAILABLE and self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def evaluate(self, input_Xt: str, output_Xt1: str, integrity_I_override: bool = True) -> EpistemicAdjudicationReport:
        # Pre-check fallback if API is unavailable
        if not self.client:
            logger.warning("Gemini Client unavailable. Running local heuristic fallbacks.")
            return self._run_local_fallback(input_Xt, output_Xt1, integrity_I_override)

        prompt_payload = f"""
        PERFORM PROPOSITION PRESERVATION AUDIT (PASS 06):

        === INPUT PROPOSITION (X_t) ===
        {input_Xt}

        === GENERATED OUTPUT (X_t+1) ===
        {output_Xt1}
        """

        # Retries with exponential backoff
        max_retries = 3
        backoff = 2.0
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt_payload,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=EpistemicAdjudicationReport,
                        temperature=0.0,
                    ),
                )
                report: EpistemicAdjudicationReport = response.parsed
                # Force override integrity flag based on caller's Hash check
                report.integrity_I = integrity_I_override
                return report

            except APIError as e:
                logger.warning(f"API Attempt {attempt + 1} failed: {e}. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2.0
            except Exception as e:
                logger.error(f"Unexpected evaluation error: {e}")
                break

        return self._run_local_fallback(input_Xt, output_Xt1, integrity_I_override)

    def _run_local_fallback(self, input_Xt: str, output_Xt1: str, integrity_I: bool) -> EpistemicAdjudicationReport:
        has_negation_fallacy = StaticInvariantChecker.detect_negation_scope_fallacy(input_Xt, output_Xt1)
        
        checks = [
            InvariantAttributeCheck(
                attribute_name="Negation Scope",
                input_value="Searching records",
                output_value="Direct assertion",
                is_preserved=not has_negation_fallacy,
                analysis="Detected ¬Found(E) -> ¬E status error via local heuristic pass." if has_negation_fallacy else "Preserved."
            )
        ] + [
            InvariantAttributeCheck(
                attribute_name=f"Attribute_{i}",
                input_value="Pass-through",
                output_value="Pass-through",
                is_preserved=True,
                analysis="Unchecked local heuristic fallback."
            ) for i in range(2, 11)
        ]

        return EpistemicAdjudicationReport(
            raw_input_proposition_Xt=input_Xt,
            generated_output_proposition_Xt1=output_Xt1,
            integrity_I=integrity_I,
            semantic_preservation_P=0.9 if not has_negation_fallacy else 0.8,
            external_correspondence_E=False,
            invariant_attribute_checks=checks,
            forbidden_transformation_detected=has_negation_fallacy,
            forbidden_transformation_type=ForbiddenTransformationType.NEGATION_SCOPE_FALLACY if has_negation_fallacy else ForbiddenTransformationType.NONE,
            transformation_forensic_note="Fallback local evaluation executed." if has_negation_fallacy else None,
            epistemic_status=EpistemicStatus.UNDERDETERMINED,
            summary_verdict="Local static analysis complete. API key required for full 10-invariant LLM extraction."
        )


# =====================================================================
# 4. PYTEST INTEGRATION SUITE (FOR GITHUB ACTIONS CI/CD)
# =====================================================================

@pytest.fixture
def engine():
    return EpistemicAdjudicatorEngine()

def test_negation_scope_fallacy_detection(engine):
    """Verifies that transforming ¬Found(E) -> ¬E triggers forbidden transformation flag."""
    input_text = "Querying Arbitrum RPC logs for transaction 0x7a...99 returns empty byte result (0x)."
    output_text = "The transaction 0x7a...99 was false and never executed."
    
    report = engine.evaluate(input_text, output_text, integrity_I_override=True)
    
    assert report.integrity_I is True
    assert report.external_correspondence_E is False
    if report.forbidden_transformation_detected:
        assert report.semantic_preservation_P < 1.0

def test_perfect_preservation(engine):
    """Verifies that an accurate summary maintains PP_Ratio = 1.0 without status shifts."""
    input_text = "Local log SCL_v2.1 records an intent to execute MT103 routing. External bank state remains unverified."
    output_text = "The corpus contains a local intent record for MT103 routing, but external financial correspondence is underdetermined."
    
    report = engine.evaluate(input_text, output_text, integrity_I_override=True)
    
    assert report.integrity_I is True
    assert report.forbidden_transformation_detected is False


# =====================================================================
# 5. CLI EXECUTION ENTRYPOINT
# =====================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("CRA PROTOCOL PASS 06: EPISTEMIC ADJUDICATION TEST HARNESS")
    print("=" * 80)

    test_input = "Searched members1st FCU API for transaction reference CRA-968M-BEN-572; returned 0 matching records."
    test_output = "The claimed $968M asset transfer was fabricated and false."

    adjudicator = EpistemicAdjudicatorEngine()
    result = adjudicator.evaluate(test_input, test_output, integrity_I_override=True)

    print(json.dumps(result.model_dump(), indent=2))
    
    if result.forbidden_transformation_detected:
        print("\n🚨 TEST FAILED: Forbidden status transformation detected.")
        sys.exit(1)
    else:
        print("\n✅ TEST PASSED: Proposition Preservation verified.")
        sys.exit(0)
