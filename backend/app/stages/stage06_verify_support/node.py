"""
Stage 6 - Supportive Verification (지지 관점 검증)

주장을 지지하는 관점에서 증거를 분석합니다.
SLM을 호출하여 DraftVerdict를 생성합니다.

Input state keys:
    - trace_id: str
    - claim_text: str
    - language: "ko" | "en" (default: "ko")
    - evidence_topk: list[dict] (evid_id, title, url, snippet, source_type)

Output state keys:
    - verdict_support: DraftVerdict dict
"""

import logging
from pathlib import Path
from functools import lru_cache

from app.stages._shared.slm_client import call_slm2, SLMError
from app.stages._shared.guardrails import (
    parse_json_with_retry,
    build_draft_verdict,
    JSONParseError,
)

logger = logging.getLogger(__name__)

# 프롬프트 파일 경로
PROMPT_FILE = Path(__file__).parent / "prompt_supportive.txt"

# MVP 설정
MAX_SNIPPET_LENGTH = 500
DEFAULT_LANGUAGE = "ko"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """시스템 프롬프트 로드 (캐싱)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


def truncate_snippet(snippet: str, max_length: int = MAX_SNIPPET_LENGTH) -> str:
    """snippet을 최대 길이로 자르기."""
    if len(snippet) <= max_length:
        return snippet
    return snippet[:max_length] + "..."


def format_evidence_for_prompt(evidence_topk: list[dict]) -> str:
    """증거 리스트를 프롬프트용 텍스트로 포맷."""
    if not evidence_topk:
        return "(증거 없음)"

    lines = []
    for i, ev in enumerate(evidence_topk, 1):
        evid_id = ev.get("evid_id", f"ev_{i}")
        title = ev.get("title", "제목 없음")
        url = ev.get("url", "")
        # snippet 우선, 없으면 content 사용 (하위 호환성)
        text_content = ev.get("snippet") or ev.get("content", "")
        snippet = truncate_snippet(text_content)
        source_type = ev.get("source_type", "WEB_URL")

        lines.append(f"[{evid_id}] ({source_type}) {title}")
        if url:
            lines.append(f"    URL: {url}")
        lines.append(f"    내용: {snippet}")
        lines.append("")

    return "\n".join(lines)


def build_user_prompt(claim_text: str, evidence_topk: list[dict], language: str) -> str:
    """지지 관점 분석용 user prompt 생성."""
    evidence_text = format_evidence_for_prompt(evidence_topk)

    return f"""## 검증할 주장
{claim_text}

## 수집된 증거
{evidence_text}

## 요청
위 증거를 바탕으로 주장을 **지지하는 관점**에서 분석하고, 지정된 JSON 형식으로 결과를 출력하세요.
언어: {language}
"""


def create_fallback_verdict(reason: str) -> dict:
    """SLM 호출 실패 시 fallback verdict 생성."""
    return {
        "stance": "UNVERIFIED",
        "confidence": 0.0,
        "reasoning_bullets": [f"[시스템 오류] {reason}"],
        "citations": [],
        "weak_points": ["SLM 호출 실패로 분석 불가"],
        "followup_queries": [],
    }


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

    # 프롬프트 준비
    system_prompt = load_system_prompt()
    user_prompt = build_user_prompt(claim_text, evidence_topk, language)

    # SLM 호출 함수
    def call_fn():
        return call_slm2(system_prompt, user_prompt)

    def retry_call_fn(retry_prompt: str):
        combined_prompt = f"{system_prompt}\n\n{retry_prompt}"
        return call_slm2(combined_prompt, user_prompt)

    try:
        # JSON 파싱 with 재시도
        raw_verdict = parse_json_with_retry(call_fn, retry_call_fn=retry_call_fn)

        # 정규화 및 검증
        verdict = build_draft_verdict(raw_verdict, evidence_topk)

        logger.info(
            f"[{trace_id}] Stage6 완료: stance={verdict['stance']}, "
            f"confidence={verdict['confidence']:.2f}, "
            f"citations={len(verdict['citations'])}"
        )

    except JSONParseError as e:
        logger.error(f"[{trace_id}] JSON 파싱 최종 실패: {e}")
        verdict = create_fallback_verdict(f"JSON 파싱 실패: {e}")

    except SLMError as e:
        logger.error(f"[{trace_id}] SLM 호출 실패: {e}")
        verdict = create_fallback_verdict(f"SLM 호출 실패: {e}")

    except Exception as e:
        logger.exception(f"[{trace_id}] 예상치 못한 오류: {e}")
        verdict = create_fallback_verdict(f"내부 오류: {e}")

    state["verdict_support"] = verdict
    return state