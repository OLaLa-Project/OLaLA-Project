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


import asyncio
from app.services.web_rag_service import WebRAGService


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


async def run_async(state: dict) -> dict:
    """Stage 5 Main (Async)."""
    scored = state.get("scored_evidence", [])
    claim_text = state.get("claim_text", "")

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
    citations = []
    
    # Prepare enrichment tasks
    enrichment_tasks = []
    
    for item in final_selection:
        url = item.get("url", "")
        title = item.get("title", "")
        content = item.get("content", "")
        source_type = item.get("source_type", "WEB")

        citation = {
            # 핵심: evid_id 생성 (Stage 6/7에서 citation 검증에 사용)
            "evid_id": _generate_evid_id(url, title),
            "source_type": source_type,
            "title": title,
            "url": url,
            "content": content,
            # 핵심: snippet 생성 (Stage 6/7에서 LLM 프롬프트에 사용)
            "snippet": _create_snippet(content), # Initial snippet
            "score": item.get("score", 0.0),
            "relevance": item.get("score", 0.0),  # API 호환용
            "metadata": item.get("metadata", {}),
        }
        
        # Web RAG Enrichment
        if source_type in {"WEB_URL", "NEWS", "WEB"} and url:
            # We need to enrich this citation
            # We pass the citation dict to be modified in place
            task = WebRAGService.enrich_citation(citation, claim_text)
            enrichment_tasks.append(task)
            
        citations.append(citation)

    # Execute RAG tasks
    if enrichment_tasks:
        logger.info(f"Stage 5: Enriching {len(enrichment_tasks)} citations with Web RAG...")
        await asyncio.gather(*enrichment_tasks)
        
    # Final Standardization
    # Ensure all snippets (including Wiki and RAG-updated Web) are within limit
    for cit in citations:
        # Re-apply create_snippet to SNIPPET. 
        # Content remains as is (original summary or full text depending on source).
        # WebRAGService updates 'snippet' and optionally 'content'.
        # User requested: KEEP content as original summary, update snippet only.
        # But WebRAGService.enrich_citation currently updates BOTH.
        # We need to verify WebRAGService behavior. Uses enrich_citation.
        
        # Correction: The user wants to keep the ORIGINAL content (short summary) but have the NEW snippet (RAG).
        # However, WebRAGService.enrich_citation (as implemented) updates citation["content"] too.
        # We should modify WebRAGService? Or restore content here?
        # Restoring content is hard because we pass the dict by reference.
        # Better to modify WebRAGService to NOT update content, OR modify it here.
        # Let's check WebRAGService source again... it updates both.
        # To strictly follow user request without modifying service file immediately:
        # Actually I can modify the service file to respect a flag or just remove the content update line.
        pass # Logic handled in next tool call (WebRAGService modification)
        
        # Standardize snippet length
        current_snippet = cit.get("snippet") or ""
        cit["snippet"] = _create_snippet(current_snippet)

    logger.info(f"Stage 5 Complete. Selected {len(citations)} citations.")

    return {
        "citations": citations,
        "evidence_topk": citations,
        "scored_evidence": None,
        "risk_flags": state.get("risk_flags", []) + (["LOW_EVIDENCE"] if not citations else [])
    }


def run(state: dict) -> dict:
    """Sync wrapper for Stage 5."""
    try:
        return asyncio.run(run_async(state))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        out = loop.run_until_complete(run_async(state))
        loop.close()
        return out
