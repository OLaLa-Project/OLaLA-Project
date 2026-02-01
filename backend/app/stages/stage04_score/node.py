"""Stage 4 - Score Evidence (Hybrid Rerank)."""

import logging
from app.services.wiki_retriever import calculate_hybrid_score, extract_keywords

logger = logging.getLogger(__name__)

def run(state: dict) -> dict:
    """
    Stage 4 Main:
    1. Get 'evidence_candidates'
    2. Extract keywords from claim (for scoring)
    3. Calculate Final Score (Hybrid)
    4. Store 'scored_evidence'
    """
    candidates = state.get("evidence_candidates", [])
    claim_text = state.get("claim_text", "")
    
    # Extract keywords for scoring (Title/Lexical matching)
    keywords = extract_keywords(claim_text)
    
    scored_evidence = []
    
    logger.info(f"Stage 4 Start. Scoring {len(candidates)} candidates against claim: '{claim_text}'")

    for cand in candidates:
        if not isinstance(cand, dict):
            logger.warning("Stage 4: skipping non-dict candidate: %r", cand)
            continue
        # Prepare hit-like object for scorer
        # Wiki results have metadata, Web results need adaptation
        
        hit_for_score = {
            "title": cand.get("title", "") or "",
            "content": cand.get("content", "") or "",
            "dist": (cand.get("metadata") or {}).get("dist"),         # Only Wiki has this
            "lex_score": (cand.get("metadata") or {}).get("lex_score") # Only Wiki has this
        }

        # Calculate Score
        # Weights: Vector=0.7, Title=0.1, Lex=0.2 (Optimized Default)
        final_score = 0.0
        
        source_type = cand.get("source_type", "")
        if source_type in {"KNOWLEDGE_BASE", "KB_DOC", "WIKIPEDIA"}:
            final_score = calculate_hybrid_score(
                hit=hit_for_score, 
                keywords=keywords
                # Weights are now internal to the function (Additive Boost)
            )
        else:
             # Web Search Scoring (Simplified)
             # Assume Web Search results are generally high relevance if returned by engine.
             # Give base score + keyword overlap bonus
             content_lower = (cand.get("content") or "").lower()
             match_count = sum(1 for k in keywords if k.lower() in content_lower)
             lex_norm = min(match_count / 5.0, 1.0)
             final_score = 0.5 + (0.5 * lex_norm) # Base 0.5 guaranteed for Web

        cand["score"] = round(final_score, 4)
        scored_evidence.append(cand)

    # Update State
    state["scored_evidence"] = scored_evidence
    logger.info(f"Stage 4 Complete. Scoring finished.")
    
    return state
