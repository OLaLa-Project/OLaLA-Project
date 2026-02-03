from typing import Any, Optional, List, Dict
from sqlalchemy.orm import Session

from app.gateway.database.repos.wiki_repo import WikiRepository
# from app.gateway.database.repos.rag_repo import RagRepository # Not used here directly
from app.services.wiki_query_normalizer import normalize_question_to_query
from app.gateway.embedding.client import embed_texts, vec_to_pgvector_literal

# Logic constants
EMBED_MISSING_CAP = 300
EMBED_MISSING_BATCH = 64
SNIPPET_CHARS = 240
RERANK_OVERSAMPLE = 20 # How many times top_k to fetch for reranking

def extract_keywords(text: str) -> List[str]:
    """Simple keyword extraction."""
    return [t for t in text.replace("?", " ").split() if len(t) >= 2]

def calculate_hybrid_score(
    hit: Dict[str, Any],
    keywords: List[str],
    fts_rank: float = 0.0,
) -> float:
    """
    Calculate Hybrid Score using Additive Boosting.
    
    Base: Vector Score (1 / (1 + dist))
    Boosts: FTS Rank, Title Match, Lexical Match
    """
    # 1. Vector Score (Base)
    # dist=0.0 -> 1.0
    # dist=0.4 -> 0.71
    # dist=1.0 -> 0.5
    vec_score = 0.0
    if hit.get("dist") is not None:
         vec_score = 1.0 / (1.0 + float(hit["dist"]))

    # 2. Title Score (Boost)
    title_score = 0.0
    title_lower = hit["title"].lower()
    if keywords:
        match_count = sum(1 for k in keywords if k.lower() in title_lower)
        title_score = match_count / len(keywords)
    
    # 3. FTS key score (Boost)
    # ts_rank_cd usually returns 0.0 ~ 0.1 for simple queries, can be higher for dense matches.
    # We cap effective boost from FTS.
    norm_fts = min(fts_rank * 2.0, 1.0) # Scale up FTS rank a bit
    
    # 4. Lexical Score (Boost)
    lex_raw = hit.get("lex_score", 0.0)
    if lex_raw == 0.0 and hit.get("content"):
        content_lower = hit["content"].lower()
        lex_raw = sum(content_lower.count(k.lower()) for k in keywords)
    norm_lex = min(lex_raw / 5.0, 1.0)
    
    # Final Formula: Base + Boosts
    # We want a strong vector match (0.7) to pass 0.7 threshold easily.
    # We also want a strong FTS match to save a weak vector match.
    
    # Weights for boosting
    W_FTS = 0.3
    W_TITLE = 0.2
    W_LEX = 0.1
    
    # Calculate preliminary final score
    final_score = vec_score
    final_score += (norm_fts * W_FTS)
    final_score += (title_score * W_TITLE)
    final_score += (norm_lex * W_LEX)

    # 5. Semantic Drift Penalty (Critical Fix)
    # If Vector score is high but lexical overlap is low, it's likely a semantic drift (e.g. Nazi Party for "Worker" query)
    match_ratio = 1.0
    if hit.get("content") and keywords:
        content_lower = hit["content"].lower()
        # Check presence of each keyword
        present_keywords = sum(1 for k in keywords if k.lower() in content_lower)
        match_ratio = present_keywords / len(keywords)
        
        # Policy: If you match fewer than 30% of keywords, you are suspicious.
        # e.g. ["Coupang", "Worker", "Accident", "Coverup"] -> Match only "Worker" (25%) -> Penalty
        if len(keywords) >= 2 and match_ratio < 0.3:
            final_score *= 0.5 # Severe penalty to drop below threshold
            
    return min(final_score, 1.0)

def ensure_wiki_embeddings(
    db: Session,
    page_ids: List[int],
    max_chunks: int = 300,
    batch_size: int = 64,
) -> int:
    """Find chunks missing embeddings and generate them."""
    wiki_repo = WikiRepository(db)
    missing_chunks = wiki_repo.chunks_missing_embedding(page_ids, limit=max_chunks)
    if not missing_chunks:
        return 0

    updated_count = 0
    for i in range(0, len(missing_chunks), batch_size):
        batch = missing_chunks[i : i + batch_size]
        chunk_ids = [cid for cid, _ in batch]
        texts = [content for _, content in batch]

        # Call Embedding Gateway
        embeddings = embed_texts(texts)
        
        # Prepare updates
        updates = {}
        for cid, emb in zip(chunk_ids, embeddings):
            updates[cid] = vec_to_pgvector_literal(emb)
        
        updated_count += wiki_repo.update_chunk_embeddings(updates)
    
    return updated_count

def retrieve_wiki_hits(
    db: Session,
    question: str,
    top_k: int = 8,
    window: int = 2,
    page_limit: int = 8,
    embed_missing: bool = False,
    max_chars: Optional[int] = None,
    page_ids: Optional[List[int]] = None,
    search_mode: str = "auto",
) -> Dict[str, Any]:
    """
    Orchestrate wiki search with Hybrid Pipeline:
    1. Candidate Selection (Union: Keyword, Chunk FTS, Vector)
    2. Embedding Ensure
    3. Vector Search (High Recall / Oversample)
    4. Hybrid Rerank (Vector + FTS + Title)
    5. Context Window Fetching
    """
    repo = WikiRepository(db)
    q_norm = normalize_question_to_query(question)
    keywords = extract_keywords(q_norm)
    
    # Prepare Vector
    q_vec = embed_texts([question])[0]
    q_vec_lit = vec_to_pgvector_literal(q_vec)

    # --- 1. Candidate Selection ---
    candidates = []
    candidates_kw = []
    candidates_fts = []
    candidates_vec = []
    
    if page_ids:
        # If explicit page_ids provided
        pass 
    else:
        # A. Keyword Title Match (Lexical)
        candidates_kw = []
        if search_mode in ["auto", "lexical"]:
             candidates_kw = repo.find_pages_by_all_keywords(keywords, limit=page_limit)
        
        # B. Chunk FTS Match (FTS)
        candidates_fts = []
        if search_mode in ["auto", "fts"]:
            q_fts = " ".join(keywords) if keywords else q_norm
            candidates_fts = repo.find_candidates_by_chunk_fts(q_fts, limit=page_limit)

        # C. Vector Candidates (Vector)
        candidates_vec = []
        if search_mode in ["auto", "vector"]:
            candidates_vec = repo.vector_search_candidates(q_vec_lit, limit=page_limit)

    candidate_map = {}
    
    # 쿼리 디버깅용: 각 후보가 어떤 쿼리에 의해 검색되었는지 추적은 여기서 어려움 (Batch 검색이므로)
    # 하지만 Stage 3가 반환하는 결과에 "query" 필드를 심어주면 됨.
    
    for pid, title in candidates_kw:
        candidate_map[pid] = title
    
    for pid, title in candidates_fts:
        if pid not in candidate_map:
            candidate_map[pid] = title
    
    for pid, title in candidates_vec:
        if pid not in candidate_map:
            candidate_map[pid] = title
    
    # If specific mode yielded no results, try to respect it or fallback?
    # Current logic is Union. If mode is "vector", kw and fts are empty, so it works.
    
    candidates = [{"page_id": pid, "title": title} for pid, title in candidate_map.items()]
    
    candidate_ids = [c["page_id"] for c in candidates] or (page_ids if page_ids else [])

    # Ensure Embeddings
    updated_embeddings = 0
    if embed_missing and candidate_ids:
        updated_embeddings = ensure_wiki_embeddings(db, candidate_ids)

    # --- 2. Vector Search (Oversample) ---
    # Fetch more than needed to allow FTS reranking to promote relevant but slightly far vectors
    oversample_k = top_k * RERANK_OVERSAMPLE
    hits = repo.vector_search(q_vec_lit, top_k=oversample_k, page_ids=candidate_ids)

    # --- 2.5 FTS Fallback (Critical if embeddings are missing) ---
    if len(hits) < top_k:
        # Strategy: Prioritize chunks from "Title Match" candidates first.
        # If we have strong candidates (e.g. title "이재명 피습 사건" for query "이재명 피습"),
        # we MUST include their content.
        
        # 1. Fetch chunks from top candidates
        current_chunk_ids = {h["chunk_id"] for h in hits}
        
        # Take top 3 candidates (likely title matches)
        top_candidates = candidates[:3] 
        for cand in top_candidates:
            if len(hits) >= oversample_k: 
                break
            
            # Fetch first 2 chunks of this page (Assume intro is relevant)
            # We need a repo method for "get first chunks of page"
            # Since we don't have it handy, we use fetch_window for chunk_idx 0-1
            # Note: We need to know if chunk exists. fetch_window returns strings.
            # We need chunk metadata. 
            pass
            
        # To strictly implement this, we'd need repo.get_chunks_metadata_by_page(pid).
        # For now, let's rely on the generic FTS fallback but boost it with Candidate ID filtering?
        # A simpler approach: repo.find_chunks_by_fts_fallback but restrict/boost based on candidate PIDs.
        
        # Actually, let's just stick to the generic FTS fallback for now to avoid complexity explosion 
        # without defined repo methods.
        # But we can query FTS fallback with LIMIT increased, then re-sort hits in Python 
        # boosting those whose page_id is in candidates.
        
        needed = (top_k - len(hits)) * 2
        q_fts_fallback = " ".join(keywords) if keywords else question
        fts_hits = repo.find_chunks_by_fts_fallback(q_fts_fallback, limit=needed)
        
        # Boost FTS hits if they belong to candidate pages
        candidate_pids = {c["page_id"] for c in candidates}
        
        for fh in fts_hits:
            if fh["chunk_id"] not in current_chunk_ids:
                # Mock score
                score = 0.5 + (fh["lex_score"] * 0.1)
                
                # Boost if page is in candidates (Title match)
                if fh["page_id"] in candidate_pids:
                    score += 0.3
                    fh["title"] = f"★ {fh['title']}" # Debug marker
                
                fh["final_score"] = score
                hits.append(fh)
                current_chunk_ids.add(fh["chunk_id"])
    
    # --- 3. Hybrid Reranking ---
    # Calculate FTS scores for the retrieved chunks
    if hits:
        hit_chunk_ids = [h["chunk_id"] for h in hits]
        # Use q_fts or q_norm
        q_fts_rank = " ".join(keywords) if keywords else q_norm
        fts_scores = repo.calculate_fts_scores_for_chunks(hit_chunk_ids, q_fts_rank)
    else:
        fts_scores = {}

    processed_hits = []
    for h in hits:
        chunk_fts_score = fts_scores.get(h["chunk_id"], 0.0)
        
        score = calculate_hybrid_score(h, keywords, fts_rank=chunk_fts_score)
        h["final_score"] = score
        h["lex_score"] = chunk_fts_score # Show FTS rank as lexical score
        processed_hits.append(h)
    
    processed_hits.sort(key=lambda x: x["final_score"], reverse=True)
    
    # Slice to top_k after reranking
    final_hits_selection = processed_hits[:top_k]
    
    # --- 4. Context Building ---
    context_parts = []
    final_hits = []
    total_chars = 0
    
    for h in final_hits_selection:
        repo.fetch_window(h["page_id"], h["chunk_idx"] - window, h["chunk_idx"] + window)
        window_texts = repo.fetch_window(h["page_id"], h["chunk_idx"] - window, h["chunk_idx"] + window)
        full_text = "\n".join(window_texts)
        h["content"] = full_text 
        h["snippet"] = full_text[:SNIPPET_CHARS]
        
        final_hits.append(h)
        
        if max_chars is None or total_chars < max_chars:
            block = f"[{h['page_id']}] {h['title']}\n{full_text}\n"
            if max_chars is None or total_chars + len(block) <= max_chars:
                context_parts.append(block)
                total_chars += len(block)

    return {
        "question": question,
        "hits": final_hits,
        "context": "\n".join(context_parts),
        "updated_embeddings": updated_embeddings,
        "debug": {
            "mode": search_mode,
            "keywords": keywords,
            "query_used": q_fts_fallback if 'q_fts_fallback' in locals() else q_norm,
            "candidates_count": len(candidates),
        },
        "candidates": candidates,
        "prompt_context": "\n".join(context_parts),
    }
