from __future__ import annotations

import os
from typing import Any, Optional, Sequence

from sqlalchemy import bindparam, text, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.db.repo import WikiRepository, vector_literal
from app.db.repos.wiki_repo import fetch_wiki_window
from app.services.embeddings import embed_text
from app.services.wiki_embedder import ensure_wiki_embeddings, extract_keywords

EMBED_MISSING_CAP = int(os.getenv("EMBED_MISSING_CAP", "300"))
EMBED_MISSING_BATCH = int(os.getenv("EMBED_MISSING_BATCH", "64"))
LEX_CHUNK_CAP = int(os.getenv("LEX_CHUNK_CAP", "80"))
SNIPPET_CHARS = 240


def _candidate_pages_trigram(db: Session, question: str, limit: int) -> list[dict[str, Any]]:
    if not question or limit <= 0:
        return []
    sql = text("""
        SELECT page_id, title, similarity(title, :q) AS score
        FROM public.wiki_pages
        WHERE title % :q
        ORDER BY score DESC
        LIMIT :limit
    """)
    rows = db.execute(sql, {"q": question, "limit": limit}).all()
    return [{"page_id": int(r[0]), "title": str(r[1]), "score": float(r[2])} for r in rows]


def _candidate_pages_ilike(db: Session, query: str, limit: int) -> list[dict[str, Any]]:
    if not query or limit <= 0:
        return []
    sql = text("""
        SELECT page_id, title, 0.0 AS score
        FROM public.wiki_pages
        WHERE title ILIKE '%' || :q || '%'
        ORDER BY page_id
        LIMIT :limit
    """)
    rows = db.execute(sql, {"q": query, "limit": limit}).all()
    return [{"page_id": int(r[0]), "title": str(r[1]), "score": float(r[2])} for r in rows]


def _candidate_pages_keywords(repo: WikiRepository, keywords: Sequence[str], limit: int) -> list[dict[str, Any]]:
    rows = repo.find_pages_by_any_keyword(keywords, limit=limit)
    return [{"page_id": pid, "title": title, "score": 0.0} for pid, title in rows]


def _page_titles_by_ids(db: Session, page_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not page_ids:
        return []
    sql = text("""
        SELECT page_id, title
        FROM public.wiki_pages
        WHERE page_id = ANY(:pids)
        ORDER BY page_id
    """).bindparams(bindparam("pids", type_=ARRAY(BigInteger)))
    rows = db.execute(sql, {"pids": list(page_ids)}).all()
    return [{"page_id": int(r[0]), "title": str(r[1]), "score": 0.0} for r in rows]


def _lexical_chunk_hits(
    db: Session,
    page_ids: Sequence[int],
    keywords: Sequence[str],
    top_k: int,
) -> list[dict[str, Any]]:
    if not page_ids or not keywords:
        return []
    sql = text("""
        SELECT page_id, chunk_id, chunk_idx, content
        FROM public.wiki_chunks
        WHERE page_id = ANY(:pids)
        ORDER BY page_id, chunk_idx
        LIMIT :limit
    """).bindparams(bindparam("pids", type_=ARRAY(BigInteger)))
    limit = max(len(page_ids) * LEX_CHUNK_CAP, top_k)
    rows = db.execute(sql, {"pids": list(page_ids), "limit": limit}).all()

    scored: list[dict[str, Any]] = []
    lowered_keywords = [k.lower() for k in keywords]
    for page_id, chunk_id, chunk_idx, content in rows:
        text_content = content or ""
        lower = text_content.lower()
        score = sum(lower.count(k) for k in lowered_keywords)
        if score <= 0:
            continue
        scored.append(
            {
                "page_id": int(page_id),
                "chunk_id": int(chunk_id),
                "chunk_idx": int(chunk_idx),
                "content": text_content,
                "snippet": text_content[:SNIPPET_CHARS],
                "lex_score": float(score),
            }
        )

    scored.sort(key=lambda x: x["lex_score"], reverse=True)
    return scored[:top_k]


def retrieve_wiki_hits(
    db: Session,
    question: str,
    top_k: int,
    window: int,
    page_limit: int,
    embed_missing: bool,
    search_mode: str = "auto",
    max_chars: Optional[int] = None,
    page_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    repo = WikiRepository(db)
    debug: dict[str, Any] = {"search_mode": search_mode}
    
    # 1. Candidate Selection based on search_mode
    candidates: list[dict[str, Any]] = []
    
    if page_ids:
        candidates = _page_titles_by_ids(db, page_ids)
        debug["candidate_strategy"] = "page_ids"
    elif search_mode == "fts":
        # Check if FTS function exists or implement basic FTS via repo if needed
        # For now, fallback to trigram -> keyword -> ilike as FTS-lite
        candidates = _candidate_pages_trigram(db, question, page_limit)
        if not candidates:
             keywords = extract_keywords(question)
             if keywords:
                 candidates = _candidate_pages_keywords(repo, keywords, page_limit)
        if not candidates:
             candidates = _candidate_pages_ilike(db, question, page_limit)
        debug["candidate_strategy"] = "fts_fallback_chain"
    elif search_mode == "lexical":
        keywords = extract_keywords(question)
        if keywords:
            candidates = _candidate_pages_keywords(repo, keywords, limit=page_limit)
        if not candidates:
             candidates = _candidate_pages_ilike(db, question, page_limit)
        debug["candidate_strategy"] = "lexical_keywords"
    else: # auto or vector
        # Default Auto Logic: Trigram -> Keyword -> ILIKE
        candidates = _candidate_pages_trigram(db, question, page_limit)
        if not candidates:
            keywords = extract_keywords(question)
            if keywords:
                candidates = _candidate_pages_keywords(repo, keywords, page_limit)
            if not candidates:
                candidates = _candidate_pages_ilike(db, question, page_limit)
        debug["candidate_strategy"] = "auto_default"

    if not candidates:
        debug["miss"] = "no_candidates"
        return {
            "question": question,
            "candidates": [],
            "hits": [],
            "updated_embeddings": 0,
            "debug": debug,
            "context": "",
        }

    # 2. Embedding Missing Check (Lazy Build)
    candidate_page_ids = [c["page_id"] for c in candidates]
    updated_embeddings = 0
    if embed_missing and candidate_page_ids:
        updated_embeddings = ensure_wiki_embeddings(
            db,
            repo,
            candidate_page_ids,
            max_chunks=EMBED_MISSING_CAP,
            batch_size=EMBED_MISSING_BATCH,
        )

    # 3. Hits Retrieval (Vector vs Lexical vs FTS)
    hits: list[dict[str, Any]] = []
    
    # Decide strategy based on mode
    use_vector = search_mode in ["auto", "vector"]
    
    if use_vector:
        qvec_literal = vector_literal(embed_text([question])[0])
        # Oversample for reranking
        vec_hits = repo.vector_search(qvec_literal, top_k=top_k * 3, page_ids=candidate_page_ids)
        
        if vec_hits:
            for h in vec_hits:
                hits.append({
                    "title": h.title,
                    "page_id": h.page_id,
                    "chunk_id": h.chunk_id,
                    "chunk_idx": h.chunk_idx,
                    "content": h.content,
                    "snippet": h.content[:SNIPPET_CHARS],
                    "dist": float(h.dist),
                    "lex_score": 0.0, # Will be calculated in Hybrid Score
                })
        else:
             debug["vector_miss"] = True
             # Vector failed, fallback if auto
             if search_mode == "auto":
                 use_vector = False # Trigger fallback below

    if not use_vector: # Lexical fallback or explicit mode
        keywords = extract_keywords(question)
        lex_hits = _lexical_chunk_hits(db, candidate_page_ids, keywords, top_k=top_k)
        for h in lex_hits:
            hits.append({
                "title": next((c["title"] for c in candidates if c["page_id"] == h["page_id"]), ""),
                "page_id": h["page_id"],
                "chunk_id": h["chunk_id"],
                "chunk_idx": h["chunk_idx"],
                "content": h["content"],
                "snippet": h["snippet"],
                "dist": None,
                "lex_score": h["lex_score"],
            })

    # 4. Window Expansion & Formatting
    hits_with_window: list[dict[str, Any]] = []
    for h in hits:
        window_text = fetch_wiki_window(
            db,
            page_id=h["page_id"],
            center_idx=h["chunk_idx"],
            window=window,
            max_chars=2000,
        )
        hits_with_window.append({
            "title": h["title"],
            "page_id": h["page_id"],
            "chunk_id": h["chunk_id"],
            "chunk_idx": h["chunk_idx"],
            "content": window_text,
            "snippet": h["snippet"],
            "dist": h["dist"],
            "lex_score": h.get("lex_score", 0.0),
        })

    # 5. Context Building
    context = ""
    if max_chars:
        # Simple concatenation for context - usually used by LLM directly
        parts = []
        total = 0
        for i, h in enumerate(hits_with_window, start=1):
            block = f"[{i}] {h['title']}\n{h['content']}\n"
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)
        context = "\n".join(parts)

    return {
        "question": question,
        "candidates": candidates,
        "hits": hits_with_window,
        "updated_embeddings": updated_embeddings,
        "debug": debug,
        "context": context,
    }

def calculate_hybrid_score(
    hit: dict[str, Any],
    keywords: list[str],
    w_vec: float = 0.7,
    w_title: float = 0.1,
    w_lex: float = 0.2
) -> float:
    # 1. Vector Score (Distance to Similarity)
    # Cosine distance: 0 (same) to 2 (opposite). approx sim = 1 / (1 + dist)
    vec_score = 0.0
    if hit.get("dist") is not None:
         vec_score = 1.0 / (1.0 + float(hit["dist"]))

    # 2. Title Score
    title_score = 0.0
    title_lower = hit["title"].lower()
    match_count = sum(1 for k in keywords if k.lower() in title_lower)
    if keywords:
        title_score = match_count / len(keywords)
    
    # 3. Lexical Score (Keyword Density in Content)
    # Already partially calculated in lex_score for lexical hits, but recalculate for vector hits
    lex_raw = hit.get("lex_score", 0.0)
    if lex_raw == 0.0 and hit.get("content"):
        content_lower = hit["content"].lower()
        lex_raw = sum(content_lower.count(k.lower()) for k in keywords)
    
    # Normalize lex_score roughly (e.g. 5 keywords match = 1.0)
    lex_score = min(lex_raw / 5.0, 1.0)
    
    final_score = (w_vec * vec_score) + (w_title * title_score) + (w_lex * lex_score)
    return float(final_score)

