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
    max_chars: Optional[int] = None,
    page_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    repo = WikiRepository(db)
    debug: dict[str, Any] = {}

    if page_ids:
        candidates = _page_titles_by_ids(db, page_ids)
        debug["lexical_mode"] = "page_ids"
    else:
        candidates = _candidate_pages_trigram(db, question, page_limit)
        debug["lexical_mode"] = "trigram"
        if not candidates:
            keywords = extract_keywords(question)
            debug["keyword_count"] = len(keywords)
            if keywords:
                candidates = _candidate_pages_keywords(repo, keywords, page_limit)
                debug["lexical_mode"] = "keyword"
            if not candidates:
                candidates = _candidate_pages_ilike(db, question, page_limit)
                debug["lexical_mode"] = "ilike"

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
    qvec_literal = vector_literal(embed_text([question])[0])
    vec_hits = repo.vector_search(qvec_literal, top_k=top_k, page_ids=candidate_page_ids)
    if vec_hits:
        for h in vec_hits:
            hits.append(
                {
                    "title": h.title,
                    "page_id": h.page_id,
                    "chunk_id": h.chunk_id,
                    "chunk_idx": h.chunk_idx,
                    "content": h.content,
                    "snippet": h.content[:SNIPPET_CHARS],
                    "dist": float(h.dist),
                    "lex_score": None,
                }
            )
    else:
        keywords = extract_keywords(question)
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
                }
            )
        if not hits:
            debug["vector_miss"] = True

    hits_with_window: list[dict[str, Any]] = []
    for h in hits:
        window_text = fetch_wiki_window(
            db,
            page_id=h["page_id"],
            center_idx=h["chunk_idx"],
            window=window,
            max_chars=2000,
        )
        hits_with_window.append(
            {
                "title": h["title"],
                "page_id": h["page_id"],
                "chunk_id": h["chunk_id"],
                "chunk_idx": h["chunk_idx"],
                "content": window_text,
                "snippet": h["snippet"],
                "dist": h["dist"],
                "lex_score": h.get("lex_score"),
            }
        )

    context = ""
    if max_chars:
        parts = []
        total = 0
        for i, h in enumerate(hits_with_window, start=1):
            block = f"[{i}] {h['title']} (page_id={h['page_id']}, chunk_id={h['chunk_id']})\n{h['content']}\n"
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
