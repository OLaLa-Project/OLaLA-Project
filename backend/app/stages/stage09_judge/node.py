"""Stage 9 - Judge (Final Verdict & Quality Gate)."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# User-defined Threshold
QUALITY_CUTOFF = 65

def run(state: dict) -> dict:
    """
    Stage 9 Main:
    1. Check Quality Score from Stage 8.
    2. Gate: If score < 65, force UNVERIFIED.
    3. Finalize Verdict (Add summary, format).
    """
    trace_id = state.get("trace_id", "unknown")
    draft = state.get("draft_verdict", {})
    quality_score = state.get("quality_score", 0)

    logger.info(f"[{trace_id}] Stage9 Start. Quality Score: {quality_score}")

    final_verdict = draft.copy()
    
    # 1. Quality Gating
    if quality_score < QUALITY_CUTOFF:
        original_stance = draft.get("stance", "UNKNOWN")
        logger.warning(
            f"[{trace_id}] Quality Score ({quality_score}) below cutoff ({QUALITY_CUTOFF}). "
            f"Downgrading {original_stance} -> UNVERIFIED."
        )
        
        final_verdict["stance"] = "UNVERIFIED"
        final_verdict["confidence"] = 0.0
        
        # Keep reasoning but add a disclaimer (User Requirement #4)
        disclaimer = f"[시스템] 품질 점수 미달({quality_score}점)로 인해 검증 불가 판정됨."
        final_verdict["reasoning_bullets"] = [disclaimer] + draft.get("reasoning_bullets", [])
        
        # Risk Flag
        state["risk_flags"] = state.get("risk_flags", []) + ["QUALITY_GATE_FAILED"]

    # 2. Final Summary Generation (Tone & Manner: Future Work)
    # For now, we construct a simple structured summary.
    stance = final_verdict.get("stance", "UNVERIFIED")
    confidence = final_verdict.get("confidence", 0.0)
    
    summary = f"본 주장에 대한 판정 결과는 '{stance}'입니다."
    if stance != "UNVERIFIED":
        summary += f" (신뢰도: {confidence:.2f})"
    
    final_verdict["summary"] = summary

    # 3. Finalize State
    state["final_verdict"] = final_verdict
    logger.info(f"[{trace_id}] Stage9 Complete. Final Stance: {final_verdict['stance']}")

    return state
