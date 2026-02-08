"""
Stage 6 - Supportive Verification (지지 관점 검증)

주장을 지지하는 관점에서 증거를 분석합니다.
SLM Client를 통해 검증을 수행합니다.

Input state keys:
    - trace_id: str
    - claim_text: str
    - language: "ko" | "en" (default: "ko")
    - evidence_topk: list[dict] (evid_id, title, url, snippet, source_type)

Output state keys:
    - verdict_support: DraftVerdict dict
"""

import logging
import json
import re
import pathlib
from typing import List, Optional

from app.core.schemas import Citation
from app.stages._shared.orchestrator_runtime import OrchestratorError
from app.stages._shared.slm_client import get_client

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "ko"


def _convert_to_citations(evidence_topk: List[dict]) -> List[Citation]:
    """evidence_topk를 Citation 객체 리스트로 변환 (Orchestrator용)."""
    citations = []
    for ev in evidence_topk:
        citations.append(
            Citation(
                source_type=ev.get("source_type", "WEB"),
                title=ev.get("title", ""),
                url=ev.get("url", ""),
                quote=ev.get("snippet") or ev.get("content", ""),
                relevance=ev.get("score", 0.0),
                evid_id=ev.get("evid_id"),
            )
        )
    return citations


def _format_citations(citations: List[Citation]) -> str:
    """Formatter for citations to match prompt expectation."""
    formatted = []
    for cit in citations:
        # [evid_id] (source_type) 제목
        #     URL: url
        #     내용: snippet
        evid_id = cit.evid_id or "unknown"
        source = cit.source_type or "WEB"
        title = cit.title or "No Title"
        url = cit.url or ""
        content = cit.quote or ""
        
        entry = f"[{evid_id}] ({source}) {title}\n    URL: {url}\n    내용: {content}"
        formatted.append(entry)
    return "\n\n".join(formatted)


def create_fallback_verdict(reason: str) -> dict:
    """Orchestrator runtime 호출 실패 시 fallback verdict 생성."""
    return {
        "stance": "UNVERIFIED",
        "confidence": 0.0,
        "reasoning_bullets": [f"[시스템 오류] {reason}"],
        "citations": [],
        "weak_points": ["SLM 호출 실패로 분석 불가"],
        "followup_queries": [],
    }


def _clean_json_response(text: str) -> str:
    """Remove markdown code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        # Remove first line (```json or ```) and last line (```)
        lines = text.splitlines()
        if len(lines) >= 2:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
    return text.strip()


def run(state: dict) -> dict:
    """
    Stage 6 실행: 지지 관점 검증.

    Args:
        state: 파이프라인 상태 dict

    Returns:
        verdict_support가 추가된 state
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    language = state.get("language", DEFAULT_LANGUAGE)
    evidence_topk = state.get("evidence_topk", [])

    logger.info(f"[{trace_id}] Stage6 시작: claim={claim_text[:50]}...")

    # 증거가 없으면 바로 UNVERIFIED
    if not evidence_topk:
        logger.warning(f"[{trace_id}] 증거 없음, UNVERIFIED 반환")
        state["verdict_support"] = create_fallback_verdict("증거가 제공되지 않음")
        return state

    try:
        # 증거 변환
        citations = _convert_to_citations(evidence_topk)
        citations_text = _format_citations(citations)
        
        # 프롬프트 템플릿 로드
        prompt_path = pathlib.Path(__file__).parent / "prompt_supportive.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            
        system_prompt = prompt_path.read_text(encoding="utf-8")
        
        # User Prompt 구성
        user_prompt = f"""
## 검증할 주장
{claim_text}

## 수집된 증거
{citations_text}
"""

        # SLM 호출
        logger.debug(f"[{trace_id}] Calling SLM2 for supportive verification")
        client = get_client("SLM2")
        response_text = client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,  # 낮은 온도로 정확도 중시
            max_tokens=1500,  # JSON 잘림 방지
        )
        
        # JSON 파싱
        cleaned_json = _clean_json_response(response_text)
        try:
            verdict = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parse Error: {e} -> Text: {response_text}")
            raise OrchestratorError(f"SLM 응답이 유효한 JSON이 아닙니다: {e}")

        # 필수 필드 확인 및 보정 (간단한 validation)
        if "stance" not in verdict:
            verdict["stance"] = "UNVERIFIED"
        
        # perspective 추가
        verdict["perspective"] = "supportive"
            
        logger.info(
            f"[{trace_id}] Stage6 완료: stance={verdict.get('stance')}, "
            f"confidence={verdict.get('confidence', 0.0)}, "
            f"citations={len(verdict.get('citations', []))}"
        )

    except OrchestratorError as e:
        logger.error(f"[{trace_id}] Orchestrator runtime 호출 실패: {e}")
        verdict = create_fallback_verdict(f"Orchestrator 오류: {e}")

    except Exception as e:
        logger.exception(f"[{trace_id}] 예상치 못한 오류: {e}")
        verdict = create_fallback_verdict(f"내부 오류: {e}")

    state["verdict_support"] = verdict
    return state
