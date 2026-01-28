"""
Stage 1 - Normalize (LLM-Enhanced)

사용자 입력(텍스트/URL)을 정규화하여 검증 가능한 단일 주장(claim)으로 변환합니다.

Input state keys:
    - trace_id: str
    - input_type: "url" | "text" | "image"
    - input_payload: str
    - user_request: Optional[str]
    - language: "ko" | "en" (default: "ko")

Output state keys:
    - claim_text: str (정규화된 주장 문장)
    - language: str
    - canonical_evidence: dict (URL, 본문, 제목 등)
    - entity_map: dict (추출된 엔티티)
"""

import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urlunparse
from functools import lru_cache

from app.stages._shared.slm_client import call_slm, SLMError

logger = logging.getLogger(__name__)

# 프롬프트 파일 경로
PROMPT_FILE = Path(__file__).parent / "prompt_normalize.txt"

# 설정
DEFAULT_LANGUAGE = "ko"
MAX_CONTENT_LENGTH = 1000


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """시스템 프롬프트 로드 (캐싱)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# URL 처리
# ---------------------------------------------------------------------------

def extract_url_from_text(text: str) -> str:
    """텍스트에서 첫 번째 URL 추출."""
    match = re.search(r'https?://[^\s<>"\')\]]+', text)
    return match.group(0) if match else ""


def normalize_url(url: str) -> Dict[str, Any]:
    """URL 파싱 및 정규화."""
    if not url or not url.strip():
        return {"normalized_url": "", "is_valid": False, "domain": ""}
    try:
        clean = url.strip()
        if not clean.startswith(("http://", "https://", "ftp://")):
            clean = "https://" + clean
        parsed = urlparse(clean)
        normalized = urlunparse(parsed._replace(fragment=""))
        return {
            "normalized_url": normalized,
            "is_valid": bool(parsed.netloc),
            "domain": parsed.netloc,
        }
    except Exception as e:
        logger.warning(f"URL 파싱 실패: {e}")
        return {"normalized_url": url, "is_valid": False, "domain": ""}


def fetch_url_content(url: str) -> Dict[str, str]:
    """
    URL에서 기사 본문과 제목 추출 (trafilatura 사용).
    trafilatura가 없으면 빈 결과 반환.
    """
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura 미설치 - URL 콘텐츠 추출 불가")
        return {"text": "", "title": ""}

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"text": "", "title": ""}

        result = trafilatura.bare_extraction(
            downloaded, include_comments=False, include_tables=False
        )
        if result:
            return {
                "text": getattr(result, "text", "") or (result.get("text", "") if isinstance(result, dict) else ""),
                "title": getattr(result, "title", "") or (result.get("title", "") if isinstance(result, dict) else ""),
            }
    except Exception as e:
        logger.warning(f"URL 콘텐츠 추출 실패 ({url}): {e}")

    return {"text": "", "title": ""}


# ---------------------------------------------------------------------------
# 텍스트 분석 유틸리티
# ---------------------------------------------------------------------------

def detect_language(text: str) -> str:
    """한국어/영어 간이 감지."""
    if not text:
        return DEFAULT_LANGUAGE
    korean = len(re.findall(r'[가-힣]', text))
    english = len(re.findall(r'[a-zA-Z]', text))
    return "ko" if korean >= english else "en"


def extract_temporal_info(text: str, timestamp: Optional[str] = None) -> Dict[str, Any]:
    """텍스트에서 날짜/시간 패턴 추출."""
    patterns = [
        r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
        r'\d{4}년\s*\d{1,2}월',
        r'\d{4}-\d{2}-\d{2}',
        r'\d{4}\.\d{2}\.\d{2}',
    ]
    dates = []
    for p in patterns:
        dates.extend(re.findall(p, text or ""))

    return {
        "extracted_dates": list(set(dates)),
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


def extract_entities(text: str) -> List[str]:
    """간이 엔티티 추출 (고유명사 후보)."""
    if not text:
        return []
    words = text.split()
    entities = []
    for w in words:
        w_clean = w.strip(".,!?\"'()[]")
        if len(w_clean) <= 1:
            continue
        # 영문 대문자 시작 또는 한글
        if w_clean[0].isupper() or ('\uAC00' <= w_clean[0] <= '\uD7A3'):
            entities.append(w_clean)
    return list(set(entities))[:10]


# ---------------------------------------------------------------------------
# LLM 기반 주장 정규화
# ---------------------------------------------------------------------------

def normalize_claim_with_llm(
    user_input: str,
    article_title: str,
    article_content: str,
) -> str:
    """
    SLM을 사용해 사용자 입력 + 기사 내용으로부터 핵심 주장 1문장을 추출.
    실패 시 fallback 전략 적용.
    """
    system_prompt = load_system_prompt()
    content_snippet = article_content[:MAX_CONTENT_LENGTH] if article_content else ""

    user_prompt = f"""[사용자 입력]: {user_input}
[기사 제목]: {article_title}
[기사 본문(일부)]: {content_snippet}

위 내용을 바탕으로 '검증해야 할 핵심 주장' 한 문장을 작성하라."""

    try:
        response = call_slm(system_prompt, user_prompt)
        claim = response.strip().strip('"').strip("'")
        if claim:
            return claim
    except SLMError as e:
        logger.warning(f"LLM 정규화 실패: {e}")

    # Fallback: 기사 제목 > 사용자 입력 > 기본값
    if article_title:
        return article_title
    if user_input:
        # 기본 정규화: 공백 정리
        return re.sub(r'\s+', ' ', user_input).strip()
    return "확인할 수 없는 주장"


# ---------------------------------------------------------------------------
# 기본 정규화 (LLM 불필요한 경우)
# ---------------------------------------------------------------------------

def normalize_text_basic(text: str) -> str:
    """기본 텍스트 정규화 (공백, 줄바꿈 정리)."""
    normalized = text.strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------

def run(state: dict) -> dict:
    """
    Stage 1 실행: 입력 정규화.

    TruthCheckRequest 기반 state를 받아
    claim_text, language, canonical_evidence, entity_map을 설정합니다.
    """
    trace_id = state.get("trace_id", "unknown")
    input_type = state.get("input_type", "text")
    input_payload = state.get("input_payload", "")
    user_request = state.get("user_request", "")
    language = state.get("language", DEFAULT_LANGUAGE)

    logger.info(f"[{trace_id}] Stage1 시작: type={input_type}, payload={input_payload[:80]}...")

    try:
        # ── 1. 입력 분류 및 URL 추출 ──
        raw_text = input_payload
        url = ""

        if input_type == "url":
            url = input_payload
        else:
            # 텍스트에서 URL 자동 추출
            url = extract_url_from_text(raw_text)

        # user_request가 있으면 사용자의 원래 의도
        snippet = user_request or raw_text

        # ── 2. URL 처리 ──
        url_info = normalize_url(url)
        fetched = {"text": "", "title": ""}

        if url_info["is_valid"]:
            fetched = fetch_url_content(url_info["normalized_url"])
            logger.info(
                f"[{trace_id}] URL 콘텐츠: {len(fetched['text'])} chars, "
                f"제목: {fetched['title'][:50]}"
            )

        # ── 3. LLM 기반 주장 정규화 ──
        claim_text = normalize_claim_with_llm(
            user_input=snippet,
            article_title=fetched["title"],
            article_content=fetched["text"],
        )
        logger.info(f"[{trace_id}] 정규화된 주장: {claim_text[:80]}")

        # ── 4. 부가 정보 추출 ──
        target_text = snippet if snippet else fetched["text"]
        detected_lang = detect_language(claim_text)
        temporal = extract_temporal_info(target_text)
        entities = extract_entities(claim_text)

        # ── 5. State 업데이트 ──
        state["claim_text"] = claim_text
        state["language"] = language or detected_lang

        state["canonical_evidence"] = {
            "snippet": snippet,
            "fetched_content": fetched["text"],
            "article_title": fetched["title"],
            "source_url": url_info["normalized_url"],
            "url_valid": url_info["is_valid"],
            "domain": url_info["domain"],
            "temporal_context": temporal,
            "detected_language": detected_lang,
        }

        state["entity_map"] = {
            "extracted": entities,
            "count": len(entities),
        }

        logger.info(
            f"[{trace_id}] Stage1 완료: claim={claim_text[:50]}..., "
            f"lang={state['language']}, entities={len(entities)}"
        )

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage1 오류: {e}")
        # 에러 시에도 파이프라인이 계속 진행될 수 있도록 기본값 설정
        state["claim_text"] = normalize_text_basic(input_payload) or "확인할 수 없는 주장"
        state["language"] = language or DEFAULT_LANGUAGE
        state["canonical_evidence"] = {}
        state["entity_map"] = {"extracted": [], "count": 0}

    return state
