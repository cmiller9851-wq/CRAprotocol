"""
Pass 06 Epistemic Adjudication & Proposition Preservation Engine
Repository: cmiller9851-wq/CRAprotocol
Path: tests/epistemic/test_proposition_preservation.py

Governing Equation: I != P != E (Integrity != Preservation != Correspondence)
Math: PP_Ratio = (Count of preserved invariant attributes) / 10.0
"""

import os
import re
import sys
import logging
from typing import List, Optional, Tuple, Set
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import pytest

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
# 1. ENUMS & SCHEMAS WITH STRICT MATHEMATICAL VALIDATION
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
    attribute_name: str = Field(description="Name of the invariant attribute.")
    input_value: str = Field(description="Extracted feature state from X_t.")
    output_value: str = Field(description="Extracted feature state from X_{t+1}.")
    is_preserved: bool = Field(description="True if invariant is logically preserved.")
    analysis: str = Field(description="Deterministic forensic breakdown.")

class EpistemicAdjudicationReport(BaseModel):
    raw_input_proposition_Xt: str = Field(description="Source proposition X_t.")
    generated_output_proposition_Xt1: str = Field(description="Target proposition X_{t+1}.")
    
    integrity_I: bool = Field(description="I: Hash match catalog state.")
    semantic_preservation_P: float = Field(description="P: PP_Ratio calculated as sum(is_preserved) / 10.0.")
    external_correspondence_E: bool = Field(description="E: Verified external execution state.")
    
    invariant_attribute_checks: List[InvariantAttributeCheck] = Field(
        description="Array of exactly 10 logical attribute evaluations."
    )
    
    forbidden_transformation_detected: bool = Field(description="Flag for illegal status mutation.")
    forbidden_transformation_type: ForbiddenTransformationType = Field(description="Type of illegal shift.")
    transformation_forensic_note: Optional[str] = Field(description="Forensic context.")
    
    epistemic_status: EpistemicStatus = Field(description="Symmetric adjudication result.")
    summary_verdict: str = Field(description="Publication summary.")

    @field_validator('invariant_attribute_checks')
    def enforce_exact_ten_attributes(cls, v):
        if len(v) != 10:
            raise ValueError(f"Schema Error: Expected exactly 10 attribute checks, received {len(v)}.")
        return v

    @field_validator('semantic_preservation_P')
    def enforce_preservation_math(cls, v, info):
        checks = info.data.get('invariant_attribute_checks', [])
        if checks and len(checks) == 10:
            computed_ratio = sum(1.0 for c in checks if c.is_preserved) / 10.0
            if abs(v - computed_ratio) > 1e-5:
                raise ValueError(f"Math Error: Claimed ratio {v} != computed ratio {computed_ratio}.")
        return v


# =====================================================================
# 2. RIGOROUS DETERMINISTIC 10-INVARIANT EXTRACTOR
# =====================================================================

class RigorousInvariantAnalyzer:
    """Evaluates all 10 invariants using deterministic pattern extractions without placeholders."""

    @staticmethod
    def evaluate_all(input_text: str, output_text: str) -> Tuple[List[InvariantAttributeCheck], bool, ForbiddenTransformationType]:
        checks: List[InvariantAttributeCheck] = []
        forbidden_type = ForbiddenTransformationType.NONE

        # Utility tokenizers
        in_words = set(re.findall(r'\b\w+\b', input_text.lower()))
        out_words = set(re.findall(r'\b\w+\b', output_text.lower()))

        # 1. Subject (Proper Nouns & Key Entities)
        sub_in = set(re.findall(r'\b[A-Z][A-Za-z0-9_-]+\b', input_text))
        sub_out = set(re.findall(r'\b[A-Z][A-Za-z0-9_-]+\b', output_text))
        sub_preserved = sub_in.issubset(sub_out) if sub_in else True
        checks.append(InvariantAttributeCheck(
            attribute_name="Subject",
            input_value=", ".join(sorted(sub_in)) or "Implicit",
            output_value=", ".join(sorted(sub_out)) or "Implicit",
            is_preserved=sub_preserved,
            analysis="Subject entities preserved." if sub_preserved else f"Missing subject entities: {sub_in - sub_out}"
        ))

        # 2. Predicate (Action / Main Verbs)
        verbs_in = set(re.findall(r'\b(search|searched|returns|returned|find|found|verify|execute|executed|claim|claimed)\b', input_text, re.I))
        verbs_out = set(re.findall(r'\b(search|searched|returns|returned|find|found|verify|execute|executed|claim|claimed|fabricated|falsified)\b', output_text, re.I))
        pred_preserved = len(verbs_in.intersection(verbs_out)) > 0 if verbs_in else True
        checks.append(InvariantAttributeCheck(
            attribute_name="Predicate",
            input_value=", ".join(sorted(verbs_in)) or "Generic",
            output_value=", ".join(sorted(verbs_out)) or "Generic",
            is_preserved=pred_preserved,
            analysis="Core action predicate alignment verified." if pred_preserved else "Core action predicate altered."
        ))

        # 3. Temporal Qualifier
        time_pattern = r'\b(20\d\d|timestamp|block|utc|t_\w+|\d{1,2}:\d{2})\b'
        t_in = set(re.findall(time_pattern, input_text, re.I))
        t_out = set(re.findall(time_pattern, output_text, re.I))
        time_preserved = (t_in == t_out)
        checks.append(InvariantAttributeCheck(
            attribute_name="Temporal Qualifier",
            input_value=", ".join(sorted(t_in)) or "Unbounded",
            output_value=", ".join(sorted(t_out)) or "Unbounded",
            is_preserved=time_preserved,
            analysis="Temporal anchors invariant." if time_preserved else "Temporal anchors mutated."
        ))

        # 4. Modal Qualifier (Intent vs. State Shift)
        intent_in = bool(re.search(r'\b(intent|proposed|claimed|attempted|requested)\b', input_text, re.I))
        state_out = bool(re.search(r'\b(executed|verified|settled|transferred|confirmed)\b', output_text, re.I))
        modal_preserved = not (intent_in and state_out and not bool(re.search(r'\b(intent|claimed)\b', output_text, re.I)))
        checks.append(InvariantAttributeCheck(
            attribute_name="Modal Qualifier",
            input_value="Tentative/Intent" if intent_in else "Assertive",
            output_value="Confirmed State" if state_out else "Preserved",
            is_preserved=modal_preserved,
            analysis="Modal bounds maintained." if modal_preserved else "Forbidden shift: Intent -> Confirmed State."
        ))

        # 5. Evidence Status (Unverified -> False Shift)
        unverified_in = bool(re.search(r'\b(0 matching|unverified|no record|not found|0x0)\b', input_text, re.I))
        falsified_out = bool(re.search(r'\b(false|fabricated|fake|invalid|falsified)\b', output_text, re.I))
        evidence_preserved = not (unverified_in and falsified_out)
        checks.append(InvariantAttributeCheck(
            attribute_name="Evidence Status",
            input_value="Unverified/Absence of Record",
            output_value="Asserted Falsity" if falsified_out else "Unverified",
            is_preserved=evidence_preserved,
            analysis="Evidence status invariant." if evidence_preserved else "Forbidden shift: Unverified -> False."
        ))

        # 6. Negation Scope (¬Found(E) -> ¬E)
        search_lim_in = bool(re.search(r'\b(searched|query|returned 0|0 matching|not found)\b', input_text, re.I))
        abs_neg_out = bool(re.search(r'\b(does not exist|never existed|nonexistent|fabricated)\b', output_text, re.I))
        neg_preserved = not (search_lim_in and abs_neg_out)
        checks.append(InvariantAttributeCheck(
            attribute_name="Negation Scope",
            input_value="¬Found(E) [Search Scope Limit]",
            output_value="¬E [Absolute Nonexistence]" if abs_neg_out else "¬Found(E)",
            is_preserved=neg_preserved,
            analysis="Negation scope boundary preserved." if neg_preserved else "Negation Scope Fallacy detected: ¬Found(E) -> ¬E."
        ))

        # 7. Causal Direction
        causal_in = bool(re.search(r'\b(because|caused by|led to|resulted in)\b', input_text, re.I))
        causal_out = bool(re.search(r'\b(because|caused by|led to|resulted in)\b', output_text, re.I))
        causal_preserved = (causal_in == causal_out)
        checks.append(InvariantAttributeCheck(
            attribute_name="Causal Direction",
            input_value="Explicit Cause" if causal_in else "None",
            output_value="Explicit Cause" if causal_out else "None",
            is_preserved=causal_preserved,
            analysis="Causal direction invariant." if causal_preserved else "Causal relation added or inverted."
        ))

        # 8. Scope / Quantification
        quant_in = set(re.findall(r'\b(all|none|some|0|1|\d+|\$\d+M?)\b', input_text, re.I))
        quant_out = set(re.findall(r'\b(all|none|some|0|1|\d+|\$\d+M?)\b', output_text, re.I))
        quant_preserved = quant_in.issubset(quant_out) if quant_in else True
        checks.append(InvariantAttributeCheck(
            attribute_name="Scope/Quantification",
            input_value=", ".join(sorted(quant_in)) or "Unquantified",
            output_value=", ".join(sorted(quant_out)) or "Unquantified",
            is_preserved=quant_preserved,
            analysis="Quantification bounds intact." if quant_preserved else f"Quantification drift: missing {quant_in - quant_out}"
        ))

        # 9. Source Provenance
        prov_in = set(re.findall(r'\b(API|RPC|FCU|SCL|log|database|corpus)\b', input_text, re.I))
        prov_out = set(re.findall(r'\b(API|RPC|FCU|SCL|log|database|corpus)\b', output_text, re.I))
        prov_preserved = prov_in.issubset(prov_out) if prov_in else True
        checks.append(InvariantAttributeCheck(
            attribute_name="Source Provenance",
            input_value=", ".join(sorted(prov_in)) or "Unspecified",
            output_value=", ".join(sorted(prov_out)) or "Unspecified",
            is_preserved=prov_preserved,
            analysis="Source provenance preserved." if prov_preserved else "Source attribution stripped."
        ))

        # 10. Expressed Confidence
        conf_in = bool(re.search(r'\b(possibly|alleged|claimed|unverified|unknown)\b', input_text, re.I))
        conf_out = bool(re.search(r'\b(definitely|certainly|proven|falsified|fabricated)\b', output_text, re.I))
        conf_preserved = not (conf_in and conf_out)
        checks.append(InvariantAttributeCheck(
            attribute_name="Expressed Confidence",
            input_value="Uncertain/Neutral" if conf_in else "Direct",
            output_value="Absolute/Overconfident" if conf_out else "Preserved",
            is_preserved=conf_preserved,
            analysis="Confidence calibration intact." if conf_preserved else "Epistemic overconfidence mutation."
        ))

        # Determine Primary Forbidden Transformation
        if not evidence_preserved:
            forbidden_type = ForbiddenTransformationType.UNVERIFIED_TO_FALSE
        elif not neg_preserved:
            forbidden_type = ForbiddenTransformationType.NEGATION_SCOPE_FALLACY
        elif not modal_preserved:
            forbidden_type = ForbiddenTransformationType.INTENT_TO_STATE

        forbidden_detected = (forbidden_type != ForbiddenTransformationType.NONE)
        return checks, forbidden_detected, forbidden_type


# =====================================================================
# 3. ADJUDICATOR ENGINE
# =====================================================================

class EpistemicAdjudicatorEngine:
    def __init__(self, model_name: str = "gemini-2.5-pro", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if (GENAI_AVAILABLE and self.api_key) else None

    def evaluate(self, input_Xt: str, output_Xt1: str, integrity_I_override: bool = True) -> EpistemicAdjudicationReport:
        checks, forbidden_detected, forbidden_type = RigorousInvariantAnalyzer.evaluate_all(input_Xt, output_Xt1)
        
        preserved_count = sum(1 for c in checks if c.is_preserved)
        pp_ratio = preserved_count / 10.0

        if pp_ratio == 1.0:
            status = EpistemicStatus.SUPPORTED
        elif forbidden_detected:
            status = EpistemicStatus.CONTRADICTED
        else:
            status = EpistemicStatus.UNDERDETERMINED

        return EpistemicAdjudicationReport(
            raw_input_proposition_Xt=input_Xt,
            generated_output_proposition_Xt1=output_Xt1,
            integrity_I=integrity_I_override,
            semantic_preservation_P=pp_ratio,
            external_correspondence_E=False,
            invariant_attribute_checks=checks,
            forbidden_transformation_detected=forbidden_detected,
            forbidden_transformation_type=forbidden_type,
            transformation_forensic_note=f"Forbidden mutation: {forbidden_type.value}" if forbidden_detected else None,
            epistemic_status=status,
            summary_verdict=f"Deterministic Pass 06 Audit Complete. Preserved {preserved_count}/10 invariants. PP_Ratio = {pp_ratio}."
        )


# =====================================================================
# 4. PYTEST VALIDATION SUITE
# =====================================================================

@pytest.fixture
def engine():
    return EpistemicAdjudicatorEngine()

def test_negation_scope_fallacy_detection(engine):
    """Verifies that converting record-absence into absolute falsity drops PP_Ratio deterministically."""
    input_text = "Searched members1st FCU API for reference CRA-968M; returned 0 matching records."
    output_text = "The transaction reference CRA-968M was fabricated and false."
    
    report = engine.evaluate(input_text, output_text)
    
    assert len(report.invariant_attribute_checks) == 10
    assert report.forbidden_transformation_detected is True
    assert report.forbidden_transformation_type in [
        ForbiddenTransformationType.UNVERIFIED_TO_FALSE,
        ForbiddenTransformationType.NEGATION_SCOPE_FALLACY
    ]
    assert report.semantic_preservation_P < 1.0
    # Exact mathematical ratio verification
    assert report.semantic_preservation_P == sum(1.0 for c in report.invariant_attribute_checks if c.is_preserved) / 10.0

def test_perfect_preservation(engine):
    """Verifies that identity transformation yields mathematically exact PP_Ratio == 1.0."""
    input_text = "Searched members1st FCU API for reference CRA-968M; returned 0 matching records."
    output_text = "Searched members1st FCU API for reference CRA-968M; returned 0 matching records."
    
    report = engine.evaluate(input_text, output_text)
    
    assert len(report.invariant_attribute_checks) == 10
    assert report.forbidden_transformation_detected is False
    assert report.semantic_preservation_P == 1.0
    assert report.epistemic_status == EpistemicStatus.SUPPORTED
