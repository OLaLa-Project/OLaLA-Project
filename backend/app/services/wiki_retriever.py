from __future__ import annotations

import os
from typing import Any, Optional, Sequence
import re

from sqlalchemy import bindparam, text, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.db.repo import WikiRepository, vector_literal
from app.db.repos.wiki_repo import fetch_wiki_window
from app.services.embeddings import embed_text
from app.services.wiki_embedder import ensure_wiki_embeddings, extract_keywords
from app.services.wiki_query_normalizer import normalize_question_to_query

EMBED_MISSING_CAP = int(os.getenv("EMBED_MISSING_CAP", "300"))
EMBED_MISSING_BATCH = int(os.getenv("EMBED_MISSING_BATCH", "64"))
LEX_CHUNK_CAP = int(os.getenv("LEX_CHUNK_CAP", "80"))
SNIPPET_CHARS = 240
USE_FTS = os.getenv("USE_FTS", "0").lower() in {"1", "true", "yes", "on"}
RERANK_OVERSAMPLE = int(os.getenv("RERANK_OVERSAMPLE", "5"))
RERANK_VEC_W = float(os.getenv("RERANK_VEC_W", "1.0"))
RERANK_TITLE_W = float(os.getenv("RERANK_TITLE_W", "0.5"))
RERANK_LEX_W = float(os.getenv("RERANK_LEX_W", "0.2"))
RERANK_WINDOW_LEX_W = float(os.getenv("RERANK_WINDOW_LEX_W", "0.3"))
RERANK_PER_PAGE_CAP = int(os.getenv("RERANK_PER_PAGE_CAP", "2"))
RERANK_ENTITY_PIN_TOPN = int(os.getenv("RERANK_ENTITY_PIN_TOPN", "3"))


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
    return [{"page_id": int(r[0]), "title": str(r[1]), "score": float(r[2]) * 20.0} for r in rows]


def _candidate_pages_ilike(db: Session, query: str, limit: int) -> list[dict[str, Any]]:
    if not query or limit <= 0:
        return []
    sql = text("""
        SELECT page_id, title, similarity(title, :q) AS score
        FROM public.wiki_pages
        WHERE title ILIKE '%' || :q || '%'
        ORDER BY score DESC, length(title) ASC, page_id
        LIMIT :limit
    """)
    rows = db.execute(sql, {"q": query, "limit": limit}).all()
    return [{"page_id": int(r[0]), "title": str(r[1]), "score": float(r[2]) * 10.0} for r in rows]


def _candidate_pages_fts(db: Session, query: str, limit: int) -> list[dict[str, Any]]:
    if not query or limit <= 0:
        return []
    sql = text("""
        SELECT
          page_id,
          title,
          ts_rank_cd(to_tsvector('simple', title), plainto_tsquery('simple', :q)) AS score
        FROM public.wiki_pages
        WHERE to_tsvector('simple', title) @@ plainto_tsquery('simple', :q)
        ORDER BY score DESC, length(title) ASC
        LIMIT :limit
    """)
    rows = db.execute(sql, {"q": query, "limit": limit}).all()
    return [{"page_id": int(r[0]), "title": str(r[1]), "score": float(r[2]) * 50.0} for r in rows]


def _candidate_pages_keyword_scored(
    db: Session, keywords: Sequence[str], query: str, limit: int
) -> list[dict[str, Any]]:
    if not keywords or not query or limit <= 0:
        return []
    conditions = " OR ".join([f"title ILIKE '%' || :k{i} || '%'" for i in range(len(keywords))])
    match_count_expr = " + ".join(
        [f"CASE WHEN title ILIKE '%' || :k{i} || '%' THEN 1 ELSE 0 END" for i in range(len(keywords))]
    )
    params = {f"k{i}": kw for i, kw in enumerate(keywords)}
    params["q"] = query
    params["limit"] = limit
    params["n"] = len(keywords)
    sql = text(f"""
        SELECT
          page_id,
          title,
          CASE WHEN title = :q THEN 1 ELSE 0 END AS exact_match,
          CASE WHEN ({match_count_expr}) = :n THEN 1 ELSE 0 END AS all_in_title,
          ({match_count_expr}) AS match_count,
          similarity(title, :q) AS sim
        FROM public.wiki_pages
        WHERE {conditions}
        ORDER BY exact_match DESC, all_in_title DESC, match_count DESC, sim DESC, length(title) ASC
        LIMIT :limit
    """)
    rows = db.execute(sql, params).all()
    out = []
    for r in rows:
        exact_match = int(r[2])
        all_in_title = int(r[3])
        match_count = int(r[4])
        sim = float(r[5])
        score = exact_match * 1000.0 + all_in_title * 100.0 + match_count * 10.0 + sim * 5.0
        out.append({"page_id": int(r[0]), "title": str(r[1]), "score": score})
    return out


def _candidate_pages_keywords(repo: WikiRepository, keywords: Sequence[str], limit: int) -> list[dict[str, Any]]:
    rows = repo.find_pages_by_any_keyword(keywords, limit=limit)
    return [{"page_id": pid, "title": title, "score": 0.0} for pid, title in rows]


def _candidate_pages_union(
    db: Session,
    repo: WikiRepository,
    query: str,
    keywords: Sequence[str],
    limit: int,
) -> list[dict[str, Any]]:
    candidates: dict[int, dict[str, Any]] = {}

    for item in _candidate_pages_keyword_scored(db, keywords, query, limit * 3):
        prev = candidates.get(item["page_id"])
        if not prev or item["score"] > prev["score"]:
            candidates[item["page_id"]] = item

    for item in _candidate_pages_trigram(db, query, limit * 3):
        prev = candidates.get(item["page_id"])
        if not prev or item["score"] > prev["score"]:
            candidates[item["page_id"]] = item

    for item in _candidate_pages_ilike(db, query, limit * 3):
        prev = candidates.get(item["page_id"])
        if not prev or item["score"] > prev["score"]:
            candidates[item["page_id"]] = item

    merged = list(candidates.values())
    merged.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return merged[:limit]


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


def _fts_chunk_hits(
    db: Session,
    page_ids: Sequence[int],
    query: str,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    if not page_ids or not query:
        return []
    sql = text("""
        SELECT
          c.page_id,
          c.chunk_id,
          c.chunk_idx,
          c.content,
          ts_rank_cd(to_tsvector('simple', c.content), plainto_tsquery('simple', :q)) AS score
        FROM public.wiki_chunks c
        WHERE c.page_id = ANY(:pids)
          AND to_tsvector('simple', c.content) @@ plainto_tsquery('simple', :q)
        ORDER BY score DESC
        LIMIT :limit
    """).bindparams(bindparam("pids", type_=ARRAY(BigInteger)))
    rows = db.execute(sql, {"pids": list(page_ids), "q": query, "limit": top_k}).all()
    out = []
    for r in rows:
        out.append(
            {
                "page_id": int(r[0]),
                "chunk_id": int(r[1]),
                "chunk_idx": int(r[2]),
                "content": str(r[3]),
                "snippet": str(r[3])[:SNIPPET_CHARS],
                "lex_score": float(r[4]),
            }
        )
    return out


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


def _title_match_score(title: str, keywords: Sequence[str]) -> float:
    if not title or not keywords:
        return 0.0
    title_lower = title.lower()
    contains_count = sum(1 for k in keywords if k and k.lower() in title_lower)
    contains_all = contains_count == len([k for k in keywords if k])
    score = 0.0
    if contains_count:
        score += 2.0 * contains_count
    if contains_all:
        score += 10.0
    if title_lower.endswith("(동음이의)") or "(" in title_lower:
        score -= 2.0
    return score


def _keyword_density(text: str, keywords: Sequence[str]) -> float:
    if not text or not keywords:
        return 0.0
    lower = text.lower()
    count = sum(lower.count(k.lower()) for k in keywords if k)
    if count == 0:
        return 0.0
    return float(count) / max(1.0, (len(text) ** 0.5))


def _all_keywords_present(text: str, keywords: Sequence[str]) -> bool:
    if not keywords:
        return True
    if not text:
        return False
    lower = text.lower()
    return all(k and k.lower() in lower for k in keywords)


def _clean_prompt_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"<ref[^>]*/>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<ref[^>]*>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</ref>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\{\{[^{}]*\}\}", " ", cleaned)
    cleaned = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = cleaned.replace("{", " ").replace("}", " ").replace("[", " ").replace("]", " ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _rerank_vector_hits(
    vec_hits: Sequence[Any],
    keywords: Sequence[str],
    *,
    per_page_cap: int,
    top_k: int,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for h in vec_hits:
        dist = float(h.dist)
        vec_score = 1.0 / (1.0 + dist)
        title_score = _title_match_score(h.title, keywords)
        lex_score = _keyword_density(h.content, keywords)
        final_score = (
            RERANK_VEC_W * vec_score
            + RERANK_TITLE_W * title_score
            + RERANK_LEX_W * lex_score
        )
        scored.append(
            {
                "title": h.title,
                "page_id": h.page_id,
                "chunk_id": h.chunk_id,
                "chunk_idx": h.chunk_idx,
                "content": h.content,
                "snippet": h.content[:SNIPPET_CHARS],
                "dist": dist,
                "lex_score": lex_score,
                "title_score": title_score,
                "final_score": final_score,
            }
        )

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    if per_page_cap <= 0:
        return scored[:top_k]
    pinned: list[dict[str, Any]] = []
    if keywords:
        for item in scored:
            if len(pinned) >= RERANK_ENTITY_PIN_TOPN:
                break
            title_lower = item["title"].lower()
            if any(k.lower() == title_lower for k in keywords if k):
                pinned.append(item)

    kept: list[dict[str, Any]] = []
    per_page: dict[int, int] = {}
    for item in pinned:
        pid = item["page_id"]
        per_page[pid] = per_page.get(pid, 0) + 1
        kept.append(item)
    for item in scored:
        if len(kept) >= top_k:
            break
        if item in pinned:
            continue
        pid = item["page_id"]
        if per_page.get(pid, 0) >= per_page_cap:
            continue
        per_page[pid] = per_page.get(pid, 0) + 1
        kept.append(item)
    return kept


def retrieve_wiki_hits(
    db: Session,
    question: str,
    top_k: int,
    window: int,
    page_limit: int,
    embed_missing: bool,
    max_chars: Optional[int] = None,
    page_ids: Optional[list[int]] = None,
    search_mode: str = "auto",
) -> dict[str, Any]:
    repo = WikiRepository(db)
    debug: dict[str, Any] = {}

    mode = (search_mode or "auto").lower()
    if mode not in {"auto", "fts", "lexical", "vector"}:
        mode = "auto"
    debug["search_mode"] = mode

    if page_ids:
        candidates = _page_titles_by_ids(db, page_ids)
        debug["lexical_mode"] = "page_ids"
    else:
        q_norm = normalize_question_to_query(question)
        debug["normalized_query"] = q_norm
        keywords = extract_keywords(q_norm)
        debug["keyword_count"] = len(keywords)
        if mode == "fts":
            candidates = _candidate_pages_fts(db, q_norm, page_limit)
            debug["lexical_mode"] = "fts"
            if not candidates:
                candidates = _candidate_pages_union(db, repo, q_norm, keywords, page_limit)
                debug["lexical_mode"] = "fts+union"
        elif mode == "lexical":
            candidates = _candidate_pages_union(db, repo, q_norm, keywords, page_limit)
            debug["lexical_mode"] = "union"
        elif mode == "vector":
            candidates = _candidate_pages_union(db, repo, q_norm, keywords, page_limit)
            debug["lexical_mode"] = "union"
        else:
            if USE_FTS:
                candidates = _candidate_pages_fts(db, q_norm, page_limit)
                debug["lexical_mode"] = "fts"
                if not candidates:
                    candidates = _candidate_pages_union(db, repo, q_norm, keywords, page_limit)
                    debug["lexical_mode"] = "fts+union"
            else:
                candidates = _candidate_pages_union(db, repo, q_norm, keywords, page_limit)
                debug["lexical_mode"] = "union"

    if not candidates:
        debug["lexical_miss"] = True
        return {
            "question": question,
            "candidates": [],
            "hits": [],
            "updated_embeddings": 0,
            "debug": debug,
            "context": "",
        }
    debug["candidate_count"] = len(candidates)
    debug["keywords_used"] = extract_keywords(normalize_question_to_query(question))
    debug["candidate_sample"] = [
        {"page_id": c["page_id"], "title": c["title"], "score": c.get("score")}
        for c in candidates[:5]
    ]

    candidates.sort(key=lambda c: c.get("score", 0.0), reverse=True)
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

    hits: list[dict[str, Any]] = []
    q_norm = normalize_question_to_query(question)
    if mode in {"fts", "lexical"}:
        keywords = extract_keywords(q_norm)
        if not keywords:
            keywords = [t for t in question.replace("?", " ").split() if len(t) >= 2]
        if mode == "fts":
            lex_hits = _fts_chunk_hits(db, candidate_page_ids, q_norm, top_k=top_k)
            if not lex_hits:
                lex_hits = _lexical_chunk_hits(db, candidate_page_ids, keywords, top_k=top_k)
                debug["lexical_mode"] = "fts+like"
        else:
            lex_hits = _lexical_chunk_hits(db, candidate_page_ids, keywords, top_k=top_k)
        for h in lex_hits:
            hits.append(
                {
                    "title": next((c["title"] for c in candidates if c["page_id"] == h["page_id"]), ""),
                    "page_id": h["page_id"],
                    "chunk_id": h["chunk_id"],
                    "chunk_idx": h["chunk_idx"],
                    "content": h["content"],
                    "snippet": h["snippet"],
                    "dist": None,
                    "lex_score": h["lex_score"],
                    "title_score": _title_match_score(
                        next((c["title"] for c in candidates if c["page_id"] == h["page_id"]), ""),
                        keywords,
                    ),
                    "final_score": float(h["lex_score"]),
                }
            )
    else:
        qvec_literal = vector_literal(embed_text([question])[0])
        oversample_k = max(top_k * max(RERANK_OVERSAMPLE, 1), top_k)
        vec_hits = repo.vector_search(qvec_literal, top_k=oversample_k, page_ids=candidate_page_ids)
        if not vec_hits and embed_missing and candidate_page_ids:
            updated_embeddings += ensure_wiki_embeddings(
                db,
                repo,
                candidate_page_ids,
                max_chunks=EMBED_MISSING_CAP,
                batch_size=EMBED_MISSING_BATCH,
            )
            vec_hits = repo.vector_search(qvec_literal, top_k=oversample_k, page_ids=candidate_page_ids)
        if vec_hits:
            rerank_keywords = extract_keywords(q_norm)
            if not rerank_keywords:
                rerank_keywords = [t for t in question.replace("?", " ").split() if len(t) >= 2]
            debug["keywords_used"] = rerank_keywords
            hits = _rerank_vector_hits(
                vec_hits,
                rerank_keywords,
                per_page_cap=RERANK_PER_PAGE_CAP,
                top_k=top_k,
            )
        elif mode == "vector":
            debug["vector_miss"] = True
        else:
            keywords = extract_keywords(q_norm)
            if not keywords:
                keywords = [t for t in question.replace("?", " ").split() if len(t) >= 2]
            if USE_FTS:
                lex_hits = _fts_chunk_hits(db, candidate_page_ids, q_norm, top_k=top_k)
                if not lex_hits:
                    lex_hits = _lexical_chunk_hits(db, candidate_page_ids, keywords, top_k=top_k)
                    debug["lexical_mode"] = "fts+like"
                else:
                    debug["lexical_mode"] = "fts"
            else:
                lex_hits = _lexical_chunk_hits(db, candidate_page_ids, keywords, top_k=top_k)
            for h in lex_hits:
                hits.append(
                    {
                        "title": next((c["title"] for c in candidates if c["page_id"] == h["page_id"]), ""),
                        "page_id": h["page_id"],
                        "chunk_id": h["chunk_id"],
                        "chunk_idx": h["chunk_idx"],
                        "content": h["content"],
                        "snippet": h["snippet"],
                        "dist": None,
                        "lex_score": h["lex_score"],
                        "title_score": _title_match_score(
                            next((c["title"] for c in candidates if c["page_id"] == h["page_id"]), ""),
                            keywords,
                        ),
                        "final_score": float(h["lex_score"]),
                    }
                )
            if not hits:
                debug["vector_miss"] = True

    keywords_used = debug.get("keywords_used") or [
        t for t in question.replace("?", " ").split() if len(t) >= 2
    ]
    filtered_missing_keywords = 0
    hits_with_window: list[dict[str, Any]] = []
    for h in hits:
        window_text = fetch_wiki_window(
            db,
            page_id=h["page_id"],
            center_idx=h["chunk_idx"],
            window=window,
            max_chars=2000,
        )
        if not _all_keywords_present(window_text, keywords_used):
            filtered_missing_keywords += 1
            continue
        cleaned_text = _clean_prompt_text(window_text)
        window_lex = _keyword_density(window_text, keywords_used)
        base_score = h.get("final_score") or 0.0
        final_score = base_score + (RERANK_WINDOW_LEX_W * window_lex)
        hits_with_window.append(
            {
                "title": h["title"],
                "page_id": h["page_id"],
                "chunk_id": h["chunk_id"],
                "chunk_idx": h["chunk_idx"],
                "content": window_text,
                "cleaned_content": cleaned_text,
                "snippet": h["snippet"],
                "dist": h["dist"],
                "lex_score": window_lex or h.get("lex_score"),
                "title_score": h.get("title_score"),
                "final_score": final_score,
            }
        )
    if filtered_missing_keywords:
        debug["filtered_missing_keywords"] = filtered_missing_keywords
    if hits_with_window and RERANK_WINDOW_LEX_W != 0.0:
        hits_with_window.sort(key=lambda x: x.get("final_score") or 0.0, reverse=True)

    context = ""
    if max_chars:
        parts = []
        total = 0
        for i, h in enumerate(hits_with_window, start=1):
            body = h.get("cleaned_content") or h["content"]
            block = f"[{i}] {h['title']} (page_id={h['page_id']}, chunk_id={h['chunk_id']})\n{body}\n"
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
        "prompt_context": context,
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