from __future__ import annotations
import re
from typing import Sequence
from sqlalchemy.orm import Session

from app.db.repo import WikiRepository, vector_literal
from app.services.embeddings import embed_text

_STOPWORDS = {
    "그리고","또한","또","및","에서","으로","에게","대한","관련","문제","사건","이슈","내용",
    "무엇","어떻게","왜","언제","어디","누구","정리","요약",
}

def extract_keywords(query: str, max_keywords: int = 6) -> list[str]:
    toks = re.findall(r"[0-9A-Za-z가-힣]{2,}", query)
    out, seen = [], set()
    for t in toks:
        t = t.strip()
        if not t or t in _STOPWORDS or t.isdigit() or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= max_keywords:
            break
    return out

def ensure_wiki_embeddings(
    db: Session,
    repo: WikiRepository,
    page_ids: Sequence[int],
    *,
    max_chunks: int = 2000,
    batch_size: int = 64,
    max_text_chars: int = 1800,
) -> int:
    missing = repo.chunks_missing_embedding(page_ids, limit=max_chunks)
    if not missing:
        return 0

    updated = 0
    i = 0
    while i < len(missing):
        batch = missing[i:i+batch_size]
        chunk_ids = [cid for cid, _ in batch]
        texts = [(c[:max_text_chars] if c else "") for _, c in batch]

        vecs = embed_text(texts)
        cid2vec = {cid: vector_literal(v) for cid, v in zip(chunk_ids, vecs)}
        updated += repo.update_chunk_embeddings(cid2vec)

        i += batch_size
    return updated
