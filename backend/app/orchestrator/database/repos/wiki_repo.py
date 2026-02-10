from typing import Sequence, Optional, List, Tuple, Dict
from sqlalchemy import text, bindparam, BigInteger
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import ARRAY

class WikiRepository:
    def __init__(self, db: Session):
        self.db = db

    def ping(self) -> int:
        return int(self.db.execute(text("SELECT 1")).scalar_one())

    def find_pages_by_title_ilike(self, q: str, limit: int = 50) -> List[Tuple[int, str]]:
        sql = text("""
            SELECT page_id, title
            FROM public.wiki_pages
            WHERE title ILIKE '%' || :q || '%'
            ORDER BY page_id
            LIMIT :limit
        """)
        rows = self.db.execute(sql, {"q": q, "limit": limit}).all()
        return [(int(r[0]), str(r[1])) for r in rows]

    def find_pages_by_any_keyword(self, keywords: Sequence[str], limit: int = 50) -> List[Tuple[int, str]]:
        if not keywords:
            return []
        conditions = " OR ".join([f"title ILIKE '%' || :k{i} || '%'" for i in range(len(keywords))])
        params: Dict[str, object] = {f"k{i}": kw for i, kw in enumerate(keywords)}
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

    def find_pages_by_all_keywords(self, keywords: Sequence[str], limit: int = 50) -> List[Tuple[int, str]]:
        if not keywords:
            return []
        conditions = " AND ".join([f"title ILIKE '%' || :k{i} || '%'" for i in range(len(keywords))])
        params: Dict[str, object] = {f"k{i}": kw for i, kw in enumerate(keywords)}
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
    
    def find_pages_by_fts(self, query_text: str, limit: int = 50) -> List[Tuple[int, str]]:
        """
        Full Text Search using to_tsquery and pg_trgm (if available) or generic FTS on chunks.
        The original logic likely searched chunk content or page title using tsvector.
        Assuming 'wiki_fts_idx' exists or we use simple to_tsvector match.
        """
        # Note: If specialized configuration (e.g. 'english', 'korean') was used, it should be restored.
        # Defaulting to 'simple' or standard configuration for now.
        sql = text("""
            SELECT DISTINCT p.page_id, p.title
            FROM public.wiki_pages p
            JOIN public.wiki_chunks c ON c.page_id = p.page_id
            WHERE to_tsvector('simple', c.content) @@ websearch_to_tsquery('simple', :q)
            LIMIT :limit
        """)
        # Fallback/alternative if 'simple' isn't what was used:
        # Using websearch_to_tsquery handles operators like "foo bar" -baz better.
        try:
             rows = self.db.execute(sql, {"q": query_text, "limit": limit}).all()
             return [(int(r[0]), str(r[1])) for r in rows]
        except Exception:
            # If FTS fails (e.g. syntax error or no index), return empty to be safe
            return []

    def chunks_missing_embedding(self, page_ids: Sequence[int], limit: int = 2000) -> List[Tuple[int, str]]:
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
        updated = 0
        for cid, vec_lit in chunk_id_to_vec_literal.items():
            self.db.execute(sql, {"cid": int(cid), "vec": vec_lit})
            updated += 1
        self.db.commit()
        return updated
    
    
    def fetch_window(self, page_id: int, start_idx: int, end_idx: int) -> List[str]:
        """Fetch content of chunks within a window range."""
        sql = text("""
            SELECT content
            FROM public.wiki_chunks
            WHERE page_id = :pid
              AND chunk_idx >= :start
              AND chunk_idx <= :end
            ORDER BY chunk_idx ASC
        """)
        rows = self.db.execute(sql, {"pid": page_id, "start": start_idx, "end": end_idx}).all()
        return [str(r[0]) for r in rows]

    def find_candidates_by_chunk_fts(self, query: str, limit: int = 50) -> List[Tuple[int, str]]:
        """
        Find candidates by Full Text Search on chunks.
        Returns unique page_ids with titles.
        Supports space-separated words or '&' for AND logic (Korean-friendly).
        """
        # Normalize: space-separated words to AND logic (&) for tsquery
        parts = query.replace('&', ' ').split()
        if not parts:
            return []
            
        # Build tsquery expression using bind parameters for safety
        tsquery_expr = " && ".join([f"plainto_tsquery('simple', :q{i})" for i in range(len(parts))])
        params = {f"q{i}": part for i, part in enumerate(parts)}
        params["limit"] = limit
        
        sql = text(f"""
            WITH q AS (
                SELECT {tsquery_expr} AS tsq
            ),
            matched AS (
                SELECT
                    c.page_id,
                    ts_rank_cd(to_tsvector('simple', c.content), q.tsq) AS r
                FROM public.wiki_chunks c
                CROSS JOIN q
                WHERE to_tsvector('simple', c.content) @@ q.tsq
                ORDER BY r DESC
                LIMIT :limit * 4
            )
            SELECT DISTINCT m.page_id, p.title
            FROM matched m
            JOIN public.wiki_pages p ON p.page_id = m.page_id
            LIMIT :limit
        """)
        
        try:
            rows = self.db.execute(sql, params).all()
            return [(int(r[0]), str(r[1])) for r in rows]
        except Exception as e:
            # logger.error is not defined in this file, use print or just return empty
            print(f"FTS Search Failed: {e}")
            return []

    def calculate_fts_scores_for_chunks(self, chunk_ids: Sequence[int], query: str) -> Dict[int, float]:
        """
        Calculate FTS rank for specific chunks.
        Used for re-ranking vector results.
        """
        if not chunk_ids:
            return {}
            
        sql = text("""
            WITH q AS (
                SELECT plainto_tsquery('simple', :q) AS tsq
            )
            SELECT
                c.chunk_id,
                ts_rank_cd(to_tsvector('simple', c.content), q.tsq) AS fts_rank
            FROM public.wiki_chunks c
            CROSS JOIN q
            WHERE c.chunk_id = ANY(:cids)
              AND to_tsvector('simple', c.content) @@ q.tsq
        """).bindparams(bindparam("cids", type_=ARRAY(BigInteger)))
        
        rows = self.db.execute(sql, {"cids": list(chunk_ids), "q": query}).all()
        return {int(r[0]): float(r[1]) for r in rows}


    def vector_search_candidates(self, qvec_literal: str, limit: int = 50) -> List[Tuple[int, str]]:
        """
        Get page candidates solely by vector similarity.
        Optimized to use HNSW index on chunks first.
        """
        # 1. Get top chunks using index (fetch more to ensure enough unique pages)
        sql = text("""
            WITH top_chunks AS (
                SELECT page_id
                FROM public.wiki_chunks
                ORDER BY embedding <=> (:qvec)::vector
                LIMIT :limit * 4
            )
            SELECT DISTINCT p.page_id, p.title
            FROM top_chunks c
            JOIN public.wiki_pages p ON p.page_id = c.page_id
            LIMIT :limit
        """)
        rows = self.db.execute(sql, {"qvec": qvec_literal, "limit": limit}).all()
        return [(int(r[0]), str(r[1])) for r in rows]

    def vector_search(
        self,
        qvec_literal: str,
        top_k: int = 10,
        page_ids: Optional[Sequence[int]] = None,
    ) -> List[dict]:
        """
        Returns raw rows including distance.
        """
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
            {
                "title": str(r[0]),
                "page_id": int(r[1]),
                "chunk_id": int(r[2]),
                "chunk_idx": int(r[3]),
                "content": str(r[4]),
                "dist": float(r[5]),
            }
            for r in rows
        ]
    def find_chunks_by_fts_fallback(self, query: str, limit: int = 10) -> List[dict]:
        """
        Fetch chunks directly using FTS when vector search fails.
        """
        sql = text("""
            WITH q AS (
                SELECT plainto_tsquery('simple', :q) AS tsq
            )
            SELECT
              p.title,
              c.page_id,
              c.chunk_id,
              c.chunk_idx,
              c.content,
              0.0 AS dist,
              ts_rank_cd(to_tsvector('simple', c.content), q.tsq) as rank
            FROM public.wiki_chunks c
            JOIN public.wiki_pages p ON p.page_id = c.page_id
            CROSS JOIN q
            WHERE to_tsvector('simple', c.content) @@ q.tsq
            ORDER BY rank DESC
            LIMIT :limit
        """)
        rows = self.db.execute(sql, {"q": query, "limit": limit}).all()
        return [
            {
                "title": str(r[0]),
                "page_id": int(r[1]),
                "chunk_id": int(r[2]),
                "chunk_idx": int(r[3]),
                "content": str(r[4]),
                "dist": float(r[5]),
                "lex_score": float(r[6])
            }
            for r in rows
        ]
