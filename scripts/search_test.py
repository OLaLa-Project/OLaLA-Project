#!/usr/bin/env python3
import os
import sys
import torch
from sentence_transformers import SentenceTransformer
import psycopg2
from dotenv import load_dotenv

# .env 로드
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MODEL_NAME = os.getenv("EMBED_MODEL", "dragonkue/multilingual-e5-small-ko-v2")
DB_NAME = os.getenv("POSTGRES_DB", "olala")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 search_test.py '검색어'")
        return

    query_text = sys.argv[1]
    
    print(f"Loading model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    print(f"Generating embedding for: '{query_text}'...")
    # e5 모델은 쿼리에 'query: ' 접두사가 필요할 수 있음
    embedding = model.encode(f"query: {query_text}")
    vector_str = "[" + ",".join(map(str, embedding.tolist())) + "]"

    print("Connecting to DB and searching...")
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
    cur = conn.cursor()
    
    # 인덱스 사용 여부 확인을 위해 EXPLAIN ANALYZE 포함
    search_sql = f"""
    EXPLAIN ANALYZE
    SELECT content, 1 - (embedding <=> %s::vector) as similarity
    FROM wiki_chunks
    ORDER BY embedding <=> %s::vector
    LIMIT 5;
    """
    
    cur.execute(search_sql, (vector_str, vector_str))
    rows = cur.fetchall()
    
    print("\n--- Query Plan ---")
    for row in rows:
        if isinstance(row[0], str) and "Index Scan" in row[0] or "HNSW" in row[0]:
            print(f"\033[92m{row[0]}\033[0m")
        else:
            print(row[0])

    # 실제 결과 조회
    print("\n--- Search Results ---")
    cur.execute(f"""
        SELECT content, 1 - (embedding <=> %s::vector) as similarity
        FROM wiki_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT 5;
    """, (vector_str, vector_str))
    
    for i, (content, sim) in enumerate(cur.fetchall(), 1):
        print(f"[{i}] Similarity: {sim:.4f}")
        print(f"    Content: {content[:150]}...")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
