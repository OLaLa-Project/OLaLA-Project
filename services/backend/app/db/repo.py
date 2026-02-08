from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Optional

from sqlalchemy import text, bindparam, BigInteger
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import ARRAY


def vector_literal(vec: Sequence[float], ndigits: int = 6) -> str:
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

    def find_pages_by_any_keyword(self, keywords: Sequence[str], limit: int = 50) -> list[tuple[int, str]]:
        if not keywords:
            return []
        conditions = " OR ".join([f"title ILIKE '%' || :k{i} || '%'" for i in range(len(keywords))])
        params: dict[str, object] = {f"k{i}": kw for i, kw in enumerate(keywords)}
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
        if not chunk_id_to_vec_literal:
            return 0
        sql = text("""
            UPDATE public.wiki_chunks
            SET embedding = (:vec)::vector
            WHERE chunk_id = :cid
        """)
        params = [{"cid": int(cid), "vec": vec} for cid, vec in chunk_id_to_vec_literal.items()]
        self.db.execute(sql, params)  # executemany
        self.db.commit()
        return len(params)

    def vector_search(
        self,
        qvec_literal: str,
        top_k: int = 10,
        page_ids: Optional[Sequence[int]] = None,
    ) -> list[WikiChunkRow]:
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
        return [
            WikiChunkRow(
                title=str(r[0]),
                page_id=int(r[1]),
                chunk_id=int(r[2]),
                chunk_idx=int(r[3]),
                content=str(r[4]),
                dist=float(r[5]),
            )
            for r in rows
        ]
