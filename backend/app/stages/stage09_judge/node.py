"""
Stage 9 - Judge (LLM 기반 품질 평가 + 사용자 친화적 최종 결과 생성)

LLM을 사용하여 draft_verdict의 품질을 평가하고,
사용자가 이해하기 쉬운 형태의 최종 결과물을 생성합니다.

역할 (2단계):
1. 품질 평가 (Quality Evaluation)
   - Hallucination 검사: reasoning_bullet이 citations로 뒷받침되는지
   - Grounding Precision 검사: quote가 주장과 관련있는지
   - Consistency 검사: stance가 reasoning과 일치하는지
   - Policy 검사: PII 노출, 위험 콘텐츠 여부

2. 사용자 친화적 결과 생성 (User-Friendly Output)
   - "XX% 확률로 사실입니다" 형태의 헤드라인
   - 핵심 근거와 출처 정리
   - 주의사항 및 추가 확인 권장 사항

Input state keys:
    - trace_id: str
    - claim_text: str (검증 대상 주장)
    - draft_verdict: dict (Stage 8 결과)
    - quality_score: int (Stage 8 품질 점수)
    - evidence_topk: list[dict] (Stage 5 증거/출처)
    - language: str

Output state keys:
    - final_verdict: dict (PRD 스키마 + 품질 평가 + 사용자 친화적 필드)
    - user_result: dict (클라이언트 표시용 결과)
    - risk_flags: list[str]
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from app.gateway import GatewayError
from app.gateway.llm.llm_gateway import get_llm_gateway

logger = logging.getLogger(__name__)

# 품질 게이트 임계치
QUALITY_SCORE_CUTOFF = 65


def run(state: dict) -> dict:
    """
    Stage 9 실행: 사용자 친화적 최종 결과 생성.

    Args:
        state: 파이프라인 상태 dict

    Returns:
        final_verdict와 user_result가 추가된 state
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    draft_verdict = state.get("draft_verdict", {})
    quality_score = state.get("quality_score", 0)
    evidence_topk = state.get("evidence_topk", [])
    language = state.get("language", "ko")

    logger.info(
        f"[{trace_id}] Stage9 시작: "
        f"quality_score={quality_score}, "
        f"draft_stance={draft_verdict.get('stance', 'UNKNOWN')}"
    )

    # 입력 검증
    if not draft_verdict:
        logger.warning(f"[{trace_id}] draft_verdict 없음, fallback 적용")
        fallback = _create_fallback_result("검증 데이터가 없습니다")
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = ["QUALITY_GATE_FAILED"]
        return state

    try:
        # LLM Gateway를 통한 사용자 친화적 결과 생성
        gateway = get_llm_gateway()
        judge_result = gateway.judge_verdict(
            claim_text=claim_text,
            draft_verdict=draft_verdict,
            evidence_topk=evidence_topk,
            quality_score=quality_score,
            language=language,
        )

        # 최종 결과 구성
        final_verdict = _build_final_verdict(
            judge_result=judge_result,
            draft_verdict=draft_verdict,
            evidence_topk=evidence_topk,
            trace_id=trace_id,
        )

        # 사용자 표시용 결과 (클라이언트 직접 사용)
        user_result = _build_user_result(judge_result, claim_text)

        # risk_flags 병합
        existing_flags = state.get("risk_flags", [])
        new_flags = _determine_risk_flags(judge_result, quality_score, draft_verdict)
        merged_flags = list(set(existing_flags + new_flags))

        state["final_verdict"] = final_verdict
        state["user_result"] = user_result
        state["risk_flags"] = merged_flags

        # evaluation 결과 로깅
        evaluation = judge_result.get("evaluation", {})
        logger.info(
            f"[{trace_id}] Stage9 완료: "
            f"label={judge_result.get('verdict_label')}, "
            f"confidence={judge_result.get('confidence_percent')}%, "
            f"hallucination={evaluation.get('hallucination_count', 'N/A')}, "
            f"grounding={evaluation.get('grounding_score', 'N/A')}"
        )

    except GatewayError as e:
        logger.error(f"[{trace_id}] LLM Judge 실패: {e}")
        fallback = _apply_rule_based_judge(draft_verdict, evidence_topk, quality_score, claim_text)
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = state.get("risk_flags", []) + ["LLM_JUDGE_FAILED"]

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage9 예상치 못한 오류: {e}")
        fallback = _create_fallback_result(str(e))
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = state.get("risk_flags", []) + ["QUALITY_GATE_FAILED"]

    return state


def _build_final_verdict(
    judge_result: Dict[str, Any],
    draft_verdict: Dict[str, Any],
    evidence_topk: List[Dict[str, Any]],
    trace_id: str,
) -> Dict[str, Any]:
    """PRD 스키마 + 품질 평가 + 사용자 친화적 필드를 포함한 최종 verdict."""
    # citations 변환
    raw_citations = draft_verdict.get("citations", [])
    formatted_citations = _format_citations(raw_citations, evidence_topk)

    # evaluation 추출
    evaluation = judge_result.get("evaluation", {})

    return {
        # PRD 표준 필드
        "analysis_id": trace_id,
        "label": judge_result.get("verdict_label", "UNVERIFIED"),
        "confidence": judge_result.get("confidence_percent", 0) / 100.0,
        "summary": judge_result.get("headline", ""),
        "rationale": [ev.get("point", "") for ev in judge_result.get("evidence_summary", [])],
        "citations": formatted_citations,
        "counter_evidence": [],
        "limitations": judge_result.get("cautions", []),
        "recommended_next_steps": [judge_result.get("recommendation", "")] if judge_result.get("recommendation") else [],
        "risk_flags": judge_result.get("risk_flags", []),
        "model_info": {
            "provider": "ollama",
            "model": "gemma3:4b",
            "version": "v1.0",
        },
        "latency_ms": 0,
        "cost_usd": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),

        # 품질 평가 필드 (LLM Judge 결과)
        "evaluation": {
            "hallucination_count": evaluation.get("hallucination_count", -1),
            "grounding_score": evaluation.get("grounding_score", -1.0),
            "is_consistent": evaluation.get("is_consistent"),
            "policy_violations": evaluation.get("policy_violations", []),
        },

        # 사용자 친화적 확장 필드
        "verdict_korean": judge_result.get("verdict_korean", "확인이 어렵습니다"),
        "confidence_percent": judge_result.get("confidence_percent", 0),
        "headline": judge_result.get("headline", ""),
        "explanation": judge_result.get("explanation", ""),
        "evidence_summary": judge_result.get("evidence_summary", []),
    }


def _build_user_result(judge_result: Dict[str, Any], claim_text: str) -> Dict[str, Any]:
    """
    클라이언트에서 직접 표시할 수 있는 사용자 친화적 결과.

    이 결과를 그대로 UI에 렌더링할 수 있습니다.
    """
    verdict_label = judge_result.get("verdict_label", "UNVERIFIED")
    confidence_percent = judge_result.get("confidence_percent", 0)

    # 결과 아이콘/색상 매핑
    verdict_style = {
        "TRUE": {"icon": "✅", "color": "green", "badge": "사실"},
        "FALSE": {"icon": "❌", "color": "red", "badge": "거짓"},
        "MIXED": {"icon": "⚠️", "color": "orange", "badge": "일부 사실"},
        "UNVERIFIED": {"icon": "❓", "color": "gray", "badge": "확인 불가"},
    }
    style = verdict_style.get(verdict_label, verdict_style["UNVERIFIED"])

    # 근거 목록 (출처 포함)
    evidence_list = []
    for ev in judge_result.get("evidence_summary", []):
        evidence_list.append({
            "text": ev.get("point", ""),
            "source": {
                "title": ev.get("source_title", ""),
                "url": ev.get("source_url", ""),
            }
        })

    return {
        # 헤더 영역
        "claim": claim_text,
        "verdict": {
            "label": verdict_label,
            "korean": judge_result.get("verdict_korean", "확인이 어렵습니다"),
            "confidence_percent": confidence_percent,
            "icon": style["icon"],
            "color": style["color"],
            "badge": style["badge"],
        },

        # 메인 콘텐츠
        "headline": judge_result.get("headline", ""),
        "explanation": judge_result.get("explanation", ""),

        # 근거 섹션
        "evidence": evidence_list,

        # 주의사항
        "cautions": judge_result.get("cautions", []),

        # 추가 안내
        "recommendation": judge_result.get("recommendation", ""),

        # 메타데이터
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _format_citations(
    raw_citations: List[Dict[str, Any]],
    evidence_topk: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """citations를 PRD 스키마에 맞게 변환."""
    evidence_map = {ev.get("evid_id", ""): ev for ev in evidence_topk}

    formatted = []
    for cit in raw_citations:
        evid_id = cit.get("evid_id", "")
        source_ev = evidence_map.get(evid_id, {})

        formatted.append({
            "source_type": source_ev.get("source_type", "NEWS"),
            "title": cit.get("title") or source_ev.get("title", ""),
            "url": cit.get("url") or source_ev.get("url", ""),
            "doc_id": None,
            "doc_version_id": None,
            "locator": {},
            "quote": cit.get("quote", ""),
            "relevance": source_ev.get("score", 0.0),
        })

    return formatted


def _determine_risk_flags(
    judge_result: Dict[str, Any],
    quality_score: int,
    draft_verdict: Dict[str, Any],
) -> List[str]:
    """risk_flags 결정 (LLM 결과 + 규칙 기반 병합)."""
    # LLM이 반환한 risk_flags 먼저 사용
    flags = list(judge_result.get("risk_flags", []))

    # 규칙 기반 추가 검사
    # 품질 점수 미달
    if quality_score < QUALITY_SCORE_CUTOFF:
        if "QUALITY_GATE_FAILED" not in flags:
            flags.append("QUALITY_GATE_FAILED")

    # 낮은 신뢰도
    if judge_result.get("confidence_percent", 0) < 50:
        if "LOW_CONFIDENCE" not in flags:
            flags.append("LOW_CONFIDENCE")

    # 인용 부족
    citations_count = len(draft_verdict.get("citations", []))
    if citations_count < 2:
        if "LOW_EVIDENCE" not in flags:
            flags.append("LOW_EVIDENCE")

    # UNVERIFIED 결과
    if judge_result.get("verdict_label") == "UNVERIFIED":
        if "LOW_EVIDENCE" not in flags:
            flags.append("LOW_EVIDENCE")

    # evaluation 기반 추가 검사
    evaluation = judge_result.get("evaluation", {})
    if evaluation.get("hallucination_count", 0) >= 2:
        if "HALLUCINATION_DETECTED" not in flags:
            flags.append("HALLUCINATION_DETECTED")

    if evaluation.get("policy_violations"):
        if "POLICY_RISK" not in flags:
            flags.append("POLICY_RISK")

    return flags


def _apply_rule_based_judge(
    draft_verdict: Dict[str, Any],
    evidence_topk: List[Dict[str, Any]],
    quality_score: int,
    claim_text: str,
) -> Dict[str, Any]:
    """LLM 실패 시 규칙 기반 판정."""
    stance = draft_verdict.get("stance", "UNVERIFIED")
    confidence = draft_verdict.get("confidence", 0.0)
    citations = draft_verdict.get("citations", [])

    # 품질 게이트
    if quality_score < QUALITY_SCORE_CUTOFF or not citations:
        stance = "UNVERIFIED"
        confidence = 0.0

    verdict_korean_map = {
        "TRUE": "사실입니다",
        "FALSE": "거짓입니다",
        "MIXED": "일부 사실입니다",
        "UNVERIFIED": "확인이 어렵습니다",
    }

    confidence_percent = int(confidence * 100)
    verdict_korean = verdict_korean_map.get(stance, "확인이 어렵습니다")

    # evidence_summary 생성
    evidence_map = {ev.get("evid_id", ""): ev for ev in evidence_topk}
    evidence_summary = []
    for cit in citations[:3]:
        evid_id = cit.get("evid_id", "")
        source_ev = evidence_map.get(evid_id, {})
        evidence_summary.append({
            "point": cit.get("quote", "")[:100] or "근거 확인 필요",
            "source_title": source_ev.get("title", ""),
            "source_url": source_ev.get("url", ""),
        })

    judge_result = {
        # 품질 평가 (규칙 기반 - LLM 없음)
        "evaluation": {
            "hallucination_count": -1,  # -1: 평가 불가
            "grounding_score": -1.0,
            "is_consistent": None,
            "policy_violations": [],
        },
        # 사용자 친화적 결과
        "verdict_label": stance,
        "verdict_korean": verdict_korean,
        "confidence_percent": confidence_percent,
        "headline": f"이 주장은 {confidence_percent}% 확률로 {verdict_korean}" if stance != "UNVERIFIED" else "이 주장은 현재 확인이 어렵습니다",
        "explanation": "자동 분석 시스템을 통해 검증되었습니다." if stance != "UNVERIFIED" else "충분한 근거를 확보하지 못해 확인이 어렵습니다.",
        "evidence_summary": evidence_summary,
        "cautions": ["자동 분석 결과이므로 참고용으로만 활용해 주세요"],
        "recommendation": "추가 검증을 위해 공식 출처를 직접 확인해 보시기 바랍니다.",
        "risk_flags": ["LLM_JUDGE_FAILED"],
    }

    return {
        "final_verdict": _build_final_verdict(judge_result, draft_verdict, evidence_topk, ""),
        "user_result": _build_user_result(judge_result, claim_text),
    }


def _create_fallback_result(error_msg: str) -> Dict[str, Any]:
    """에러 시 fallback 결과 생성."""
    judge_result = {
        "verdict_label": "UNVERIFIED",
        "verdict_korean": "확인이 어렵습니다",
        "confidence_percent": 0,
        "headline": "이 주장은 현재 확인이 어렵습니다",
        "explanation": f"시스템 오류로 인해 검증을 완료할 수 없습니다. ({error_msg[:50]})",
        "evidence_summary": [],
        "cautions": ["시스템 오류 발생"],
        "recommendation": "잠시 후 다시 시도하거나 직접 출처를 확인해 주세요.",
    }

    final_verdict = {
        "analysis_id": "",
        "label": "UNVERIFIED",
        "confidence": 0.0,
        "summary": judge_result["headline"],
        "rationale": [],
        "citations": [],
        "counter_evidence": [],
        "limitations": ["시스템 오류 발생"],
        "recommended_next_steps": [judge_result["recommendation"]],
        "risk_flags": ["QUALITY_GATE_FAILED"],
        "model_info": {"provider": "fallback", "model": "error", "version": "v1.0"},
        "latency_ms": 0,
        "cost_usd": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # 품질 평가 (fallback - 평가 불가)
        "evaluation": {
            "hallucination_count": -1,
            "grounding_score": -1.0,
            "is_consistent": None,
            "policy_violations": [],
        },
        "verdict_korean": "확인이 어렵습니다",
        "confidence_percent": 0,
        "headline": judge_result["headline"],
        "explanation": judge_result["explanation"],
        "evidence_summary": [],
    }

    user_result = {
        "claim": "",
        "verdict": {
            "label": "UNVERIFIED",
            "korean": "확인이 어렵습니다",
            "confidence_percent": 0,
            "icon": "❓",
            "color": "gray",
            "badge": "확인 불가",
        },
        "headline": judge_result["headline"],
        "explanation": judge_result["explanation"],
        "evidence": [],
        "cautions": judge_result["cautions"],
        "recommendation": judge_result["recommendation"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "final_verdict": final_verdict,
        "user_result": user_result,
    }
