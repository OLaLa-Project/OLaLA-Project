"""Stage 5 - Top-K Selection & Formatting."""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

THRESHOLD_SCORE = 0.7

def run(state: dict) -> dict:
    """
    Stage 5 Main:
    1. Filter candidates < 0.7
    2. Sort by score DESC
    3. Select Top K (e.g., 6)
    4. Format as 'citations' (API Schema)
    """
    scored = state.get("scored_evidence", [])
    
    logger.info(f"Stage 5 Start. Candidates: {len(scored)}, Threshold: {THRESHOLD_SCORE}")

    # 1. Filter
    filtered = [item for item in scored if item.get("score", 0.0) >= THRESHOLD_SCORE]
    
    # 2. Sort
    filtered.sort(key=lambda x: x["score"], reverse=True)
    
    # 3. Top K (Take top 6 for context window fit)
    top_k = filtered[:6]
    
    # 4. Format to Citation Schema
    # Schema: {source_type, title, url, snippet, score, ...}
    citations = []
    
    for item in top_k:
        citation = {
            "source_type": item["source_type"], # "KNOWLEDGE_BASE" or "WEB"
            "title": item["title"],
            "url": item["url"],
            "content": item["content"],         # Full content for LLM Context
            "score": item["score"],
            "metadata": item.get("metadata", {})
        }
        citations.append(citation)

    # Update State
    state["citations"] = citations
    state["evidence_topk"] = citations

    
    # Check if 'Unverified' condition met (No citations)
    if not citations:
        logger.warning("Stage 5: No evidence passed threshold. Flagging potential UNVERIFIED.")
        # Note: Stage 9 Judge will likely make the final call, but we can set a flag here.
        state["risk_flags"] = state.get("risk_flags", []) + ["LOW_EVIDENCE"]

    logger.info(f"Stage 5 Complete. Selected {len(citations)} citations.")
    
    return state
