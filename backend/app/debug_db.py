
import os
import sys
import math
from sqlalchemy import create_engine, text
from app.gateway.embedding.client import embed_texts

DATABASE_URL = "postgresql://postgres:postgres@db:5432/olala"

def check_db():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("Embedding '쿠팡'...")
        coupang_emb = embed_texts(["쿠팡"])[0]
        
        print("Embedding '이재명...'...")
        lee_text = "이재명은 다음 사람 등을 가리킨다."
        lee_emb = embed_texts([lee_text])[0]
        
        def l2_dist(v1, v2):
            return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))
            
        dist = l2_dist(coupang_emb, lee_emb)
        print(f"Distance (Coupang vs Lee): {dist}")
        
        # Check what is stored in DB for Lee
        result = conn.execute(text(f"SELECT chunk_id, embedding FROM wiki_chunks WHERE chunk_id = 198420"))
        row = result.fetchone()
        if row:
            stored_vec_str = str(row[1])
             # pgvector returns a string representation, we need to parse it if we want exact math, 
             # but we already confirmed stored == lee_emb roughly.
            print(f"Stored vector exists: {row[0]}")
            
            # If stored vector is valid, let's trust it matches lee_emb (as verified before).
            # The mystery is why this stored vector (Lee) matched Coupang query in PGVECTOR search.

            # Maybe checking pgvector operator usage in a raw query?
            # Doing a raw vector search here to reproduce using SQL.
            
            vec_literal = "[" + ",".join(str(x) for x in coupang_emb) + "]"
            search_q = f"SELECT chunk_id, content, embedding <-> '{vec_literal}' as dist FROM wiki_chunks WHERE chunk_id = 198420"
            res = conn.execute(text(search_q))
            s_row = res.fetchone()
            if s_row:
                print(f"PGVector Distance (Coupang <-> Stored Lee): {s_row[2]}")

if __name__ == "__main__":
    check_db()
