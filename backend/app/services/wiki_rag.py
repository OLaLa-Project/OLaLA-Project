# backend/app/services/wiki_rag.py
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.services.wiki_retriever import retrieve_wiki_hits


def retrieve_wiki_context(
    db: Session,
    question: str,
    top_k: int = 8,
    page_ids: Optional[list[int]] = None,
    window: int = 2,
    max_chars: int = 4200,
    page_limit: int = 8,
    embed_missing: bool = False,
    search_mode: str = "auto",
) -> dict[str, Any]:
    pack = retrieve_wiki_hits(
        db,
        question=question,
        top_k=top_k,
        window=window,
        page_limit=page_limit,
        embed_missing=embed_missing,
        max_chars=max_chars,
        page_ids=page_ids,
        search_mode=search_mode,
    )

    sources = []
    for i, h in enumerate(pack["hits"], start=1):
        sources.append(
            {
                "rank": i,
                "title": h["title"],
                "page_id": h["page_id"],
                "chunk_id": h["chunk_id"],
                "chunk_idx": h["chunk_idx"],
                "dist": h.get("dist"),
                "snippet": h.get("snippet"),
            }
        )

    return {
        "sources": sources,
        "context": pack.get("context", ""),
        "debug": pack.get("debug"),
        "prompt_context": pack.get("prompt_context"),
    }
