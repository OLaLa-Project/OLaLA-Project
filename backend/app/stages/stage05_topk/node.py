"""Stage 5 - Top-K Selection & Formatting.

Gateway 스키마를 사용하여 evid_id와 snippet을 포함한 표준 Citation 형식으로 변환합니다.

Output state keys:
    - citations: list[dict] (evid_id, title, url, content, snippet, score, ...)
    - evidence_topk: list[dict] (citations와 동일)
    - risk_flags: list[str] (LOW_EVIDENCE 플래그 추가 가능)
"""

import logging
import hashlib
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

THRESHOLD_SCORE = 0.7
TOP_K_LIMIT = 6
SNIPPET_MAX_LENGTH = 500


def _generate_evid_id(url: str, title: str) -> str:
    """URL과 제목으로 고유 evid_id 생성."""
    key = f"{url}:{title}"
    return f"ev_{hashlib.md5(key.encode()).hexdigest()[:8]}"


def _create_snippet(content: str, max_length: int = SNIPPET_MAX_LENGTH) -> str:
    """content에서 snippet 생성."""
    content = (content or "").strip()
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def run(state: dict) -> dict:
    """
    Stage 5 Main:
    1. Filter candidates < threshold
    2. Sort by score DESC
    3. Select Top K
    4. Format with evid_id and snippet (Gateway 스키마 호환)
    """
    scored = state.get("scored_evidence", [])

    logger.info(f"Stage 5 Start. Candidates: {len(scored)}, Threshold: {THRESHOLD_SCORE}")

    # 4. Filter & Sort by Group (Quota System)
    # WIKI_LIMIT = 3 (Facts)
    # NEWS_WEB_LIMIT = 3 (Recent Info)
    
    WIKI_LIMIT = 3
    NEWS_WEB_LIMIT = 3
    
    wiki_candidates = []
    news_web_candidates = []
    
    for item in scored:
        if item.get("score", 0.0) < THRESHOLD_SCORE:
            continue
            
        src = item.get("source_type", "WEB")
        if src in {"KNOWLEDGE_BASE", "WIKIPEDIA", "KB_DOC"}:
            wiki_candidates.append(item)
        else:
            news_web_candidates.append(item)
            
    # Sort each group
    wiki_candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    news_web_candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    
    # Select Top K from each according to quota
    final_selection = wiki_candidates[:WIKI_LIMIT] + news_web_candidates[:NEWS_WEB_LIMIT]
    
    # Still sort the final combined list by score for display purposes
    final_selection.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # 4. Format to Citation Schema (Gateway 호환)
    # 핵심 수정: evid_id와 snippet 필드 추가
    citations = []
    
    for item in final_selection:
        url = item.get("url", "")
        title = item.get("title", "")
        content = item.get("content", "")

        citation = {
            # 핵심: evid_id 생성 (Stage 6/7에서 citation 검증에 사용)
            "evid_id": _generate_evid_id(url, title),
            "source_type": item.get("source_type", "WEB"),
            "title": title,
            "url": url,
            "content": content,
            # 핵심: snippet 생성 (Stage 6/7에서 LLM 프롬프트에 사용)
            "snippet": _create_snippet(content),
            "score": item.get("score", 0.0),
            "relevance": item.get("score", 0.0),  # API 호환용
            "metadata": item.get("metadata", {}),
        }
        citations.append(citation)

    # Update State
    state["citations"] = citations
    state["evidence_topk"] = citations

    # Check if 'Unverified' condition met (No citations)
    if not citations:
        logger.warning("Stage 5: No evidence passed threshold. Flagging potential UNVERIFIED.")
        state["risk_flags"] = state.get("risk_flags", []) + ["LOW_EVIDENCE"]

    logger.info(f"Stage 5 Complete. Selected {len(citations)} citations.")

    return state
