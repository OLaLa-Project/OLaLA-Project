# backend/app/db/repos/wiki_repo.py
import os
from typing import Any, Optional
from sqlalchemy import text, bindparam, Integer
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

from app.services.embeddings import embed_text
from app.db.repos.rag_repo import vector_literal

EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))
EMBED_MISSING_BATCH = int(os.getenv("EMBED_MISSING_BATCH", "128"))


def search_wiki_chunks_topk(
    db: Session,
    query_vec: list[float],
    k: int = 10,
    page_ids: Optional[list[int]] = None,
    min_len: int = 80,
    snippet_chars: int = 240,
) -> list[dict[str, Any]]:
    base_sql = """
    SELECT
      p.title,
      c.page_id,
      c.chunk_id,
      c.chunk_idx,
      left(c.content, :snippet_chars) AS snippet,
      (c.embedding <=> :qvec) AS dist
    FROM public.wiki_chunks c
    JOIN public.wiki_pages p ON p.page_id = c.page_id
    WHERE c.embedding IS NOT NULL
      AND length(c.content) >= :min_len
      AND c.content !~ '^\\s*\\{\\{'  -- drop template-only chunks like {{각주}}
    """

    if page_ids:
        base_sql += " AND c.page_id = ANY(:page_ids) "

    base_sql += """
    ORDER BY c.embedding <=> :qvec
    LIMIT :k
    """

    stmt = text(base_sql).bindparams(
        bindparam("qvec", type_=Vector(EMBED_DIM)),
    )

    params: dict[str, Any] = {
        "qvec": query_vec,
        "k": k,
        "min_len": min_len,
        "snippet_chars": snippet_chars,
    }

    if page_ids:
        stmt = stmt.bindparams(bindparam("page_ids", type_=ARRAY(Integer)))
        params["page_ids"] = page_ids

    rows = db.execute(stmt, params).mappings().all()
    return [dict(r) for r in rows]


def embed_missing_chunk_embeddings(db: Session, limit: int = EMBED_MISSING_BATCH) -> int:
    if limit <= 0:
        return 0

    stmt = text("""
    SELECT chunk_id, content
    FROM public.wiki_chunks
    WHERE embedding IS NULL
      AND content IS NOT NULL
    ORDER BY chunk_id
    LIMIT :limit
    """)
    rows = db.execute(stmt, {"limit": limit}).fetchall()
    if not rows:
        return 0

    chunk_ids = []
    contents = []
    for chunk_id, content in rows:
        chunk_ids.append(int(chunk_id))
        contents.append(str(content))

    embeddings = embed_text(contents)
    update_stmt = text("""
    UPDATE public.wiki_chunks
    SET embedding = (:vec)::vector
    WHERE chunk_id = :cid
    """)
    for cid, vec in zip(chunk_ids, embeddings):
        db.execute(update_stmt, {"vec": vector_literal(vec), "cid": cid})
    db.commit()
    return len(chunk_ids)


def fetch_wiki_window(
    db: Session,
    page_id: int,
    center_idx: int,
    window: int = 2,
    max_chars: int = 2000,
) -> str:
    stmt = text("""
    SELECT content
    FROM public.wiki_chunks
    WHERE page_id = :pid
      AND chunk_idx BETWEEN :lo AND :hi
    ORDER BY chunk_idx
    """)
    lo = max(center_idx - window, 0)
    hi = center_idx + window
    rows = db.execute(stmt, {"pid": page_id, "lo": lo, "hi": hi}).fetchall()
    text_joined = "\n".join([r[0] for r in rows if r and r[0]])
    return text_joined[:max_chars]


def vector_search_with_window(
    db: Session,
    question: str,
    top_k: int = 8,
    window: int = 2,
    page_limit: int = 8,
    embed_missing: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    if embed_missing:
        embed_missing_chunk_embeddings(db)

    qvec = embed_text([question])[0]
    requested_k = min(top_k, 3)
    hits = search_wiki_chunks_topk(db, qvec, k=requested_k)

    candidates: list[dict[str, Any]] = []
    seen_pages: set[int] = set()
    hits_for_pages: list[dict[str, Any]] = []

    for chunk in hits:
        pid = chunk["page_id"]
        if pid not in seen_pages and len(seen_pages) < page_limit:
            seen_pages.add(pid)
            candidates.append({"page_id": pid, "title": chunk["title"]})
        hits_for_pages.append(chunk)

    hits_with_content: list[dict[str, Any]] = []
    for chunk in hits_for_pages:
        window_text = fetch_wiki_window(
            db,
            page_id=chunk["page_id"],
            center_idx=chunk["chunk_idx"],
            window=window,
            max_chars=2000,
        )
        hits_with_content.append(
            {
                "title": chunk["title"],
                "page_id": chunk["page_id"],
                "chunk_id": chunk["chunk_id"],
                "chunk_idx": chunk["chunk_idx"],
                "content": window_text,
                "snippet": chunk["snippet"],
                "dist": float(chunk["dist"]),
            }
        )

    return {"candidates": candidates, "hits": hits_with_content}
