from typing import Sequence, Tuple, List
from sqlalchemy import text, bindparam, BigInteger
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import ARRAY

class RagRepository:
    def __init__(self, db: Session):
        self.db = db

    def chunks_missing_embedding(self, document_ids: Sequence[int] = None, limit: int = 100) -> List[Tuple[int, str]]:
        """
        Find chunks that do not have embeddings.
        If document_ids is provided, filter by those documents.
        """
        if document_ids:
            sql = text("""
                SELECT id, content
                FROM public.rag_chunks
                WHERE document_id = ANY(:dids)
                  AND embedding IS NULL
                ORDER BY id
                LIMIT :limit
            """).bindparams(bindparam("dids", type_=ARRAY(BigInteger)))
            params = {"dids": list(document_ids), "limit": limit}
        else:
             sql = text("""
                SELECT id, content
                FROM public.rag_chunks
                WHERE embedding IS NULL
                ORDER BY id
                LIMIT :limit
            """)
             params = {"limit": limit}

        rows = self.db.execute(sql, params).all()
        return [(int(r[0]), str(r[1])) for r in rows]

    def update_chunk_embeddings(self, chunk_id_to_vec_literal: dict[int, str]) -> int:
        if not chunk_id_to_vec_literal:
            return 0
        sql = text("""
            UPDATE public.rag_chunks
            SET embedding = (:vec)::vector
            WHERE id = :cid
        """)
        updated = 0
        for cid, vec_lit in chunk_id_to_vec_literal.items():
            self.db.execute(sql, {"cid": int(cid), "vec": vec_lit})
            updated += 1
        self.db.commit()
        return updated
