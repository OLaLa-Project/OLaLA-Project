# app/db/repo.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, Optional

from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import BigInteger


def vector_literal(vec: Sequence[float], ndigits: int = 6) -> str:
    # Returns pgvector literal like: [0.1,0.2,...]
    fmt = f"{{:.{ndigits}f}}"
    return "[" + ",".join(fmt.format(float(x)) for x in vec) + "]"


@dataclass
class WikiChunkRow:
    title: str
    page_id: int
    chunk_id: int
    chunk_idx: int
    content: str
    dist: float


class WikiRepository:
    def __init__(self, db: Session):
        self.db = db

    def ping(self) -> int:
        return int(self.db.execute(text("SELECT 1")).scalar_one())

    def find_pages_by_title_ilike(self, q: str, limit: int = 50) -> list[tuple[int, str]]:
        # Simple candidate narrowing. Replace with FTS later if needed.
        sql = text("""
            SELECT page_id, title
            FROM public.wiki_pages
            WHERE title ILIKE '%' || :q || '%'
            ORDER BY page_id
            LIMIT :limit
        """)
        rows = self.db.execute(sql, {"q": q, "limit": limit}).all()
        return [(int(r[0]), str(r[1])) for r in rows]

    def find_pages_by_any_keyword(self, keywords: Sequence[str], limit: int = 50) -> list[tuple[int, str]]:
        # OR-combined ILIKE over multiple keywords
        if not keywords:
            return []
        conditions = " OR ".join([f"title ILIKE '%' || :k{i} || '%'" for i in range(len(keywords))])
        params = {f"k{i}": kw for i, kw in enumerate(keywords)}
        params["limit"] = limit
        sql = text(f"""
            SELECT page_id, title
            FROM public.wiki_pages
            WHERE {conditions}
            ORDER BY page_id
            LIMIT :limit
        """)
        rows = self.db.execute(sql, params).all()
        return [(int(r[0]), str(r[1])) for r in rows]

    def chunks_missing_embedding(self, page_ids: Sequence[int], limit: int = 2000) -> list[tuple[int, str]]:
        # Returns (chunk_id, content)
        if not page_ids:
            return []
        sql = text("""
            SELECT chunk_id, content
            FROM public.wiki_chunks
            WHERE page_id = ANY(:pids)
              AND embedding IS NULL
            ORDER BY chunk_id
            LIMIT :limit
        """).bindparams(bindparam("pids", type_=ARRAY(BigInteger)))
        rows = self.db.execute(sql, {"pids": list(page_ids), "limit": limit}).all()
        return [(int(r[0]), str(r[1])) for r in rows]

    def update_chunk_embeddings(self, chunk_id_to_vec_literal: dict[int, str]) -> int:
        # vec literal must be a string like "[0.1,0.2,...]"
        if not chunk_id_to_vec_literal:
            return 0
        sql = text("""
            UPDATE public.wiki_chunks
            SET embedding = (:vec)::vector
            WHERE chunk_id = :cid
        """)
        updated = 0
        for cid, vec_lit in chunk_id_to_vec_literal.items():
            self.db.execute(sql, {"cid": int(cid), "vec": vec_lit})
            updated += 1
        self.db.commit()
        return updated

    def vector_search(
        self,
        qvec_literal: str,
        top_k: int = 10,
        page_ids: Optional[Sequence[int]] = None,
    ) -> list[WikiChunkRow]:
        # If page_ids is None -> global search over embedded rows
        params = {"qvec": qvec_literal, "k": top_k}

        if page_ids:
            sql = text("""
                SELECT
                  p.title,
                  c.page_id,
                  c.chunk_id,
                  c.chunk_idx,
                  c.content,
                  (c.embedding <=> (:qvec)::vector) AS dist
                FROM public.wiki_chunks c
                JOIN public.wiki_pages p ON p.page_id = c.page_id
                WHERE c.embedding IS NOT NULL
                  AND c.page_id = ANY(:pids)
                ORDER BY c.embedding <=> (:qvec)::vector
                LIMIT :k
            """).bindparams(bindparam("pids", type_=ARRAY(BigInteger)))
            params["pids"] = list(page_ids)
        else:
            sql = text("""
                SELECT
                  p.title,
                  c.page_id,
                  c.chunk_id,
                  c.chunk_idx,
                  c.content,
                  (c.embedding <=> (:qvec)::vector) AS dist
                FROM public.wiki_chunks c
                JOIN public.wiki_pages p ON p.page_id = c.page_id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> (:qvec)::vector
                LIMIT :k
            """)

        rows = self.db.execute(sql, params).all()
        out: list[WikiChunkRow] = []
        for r in rows:
            out.append(
                WikiChunkRow(
                    title=str(r[0]),
                    page_id=int(r[1]),
                    chunk_id=int(r[2]),
                    chunk_idx=int(r[3]),
                    content=str(r[4]),
                    dist=float(r[5]),
                )
            )
        return out
