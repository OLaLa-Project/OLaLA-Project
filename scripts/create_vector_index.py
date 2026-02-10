#!/usr/bin/env python3
"""
Postgres(pgvector)에 HNSW 인덱스를 생성하는 스크립트.
임베딩 import가 끝난 후 실행 권장.
"""

import os
import time
import psycopg2
try:
    from dotenv import load_dotenv
except ImportError:
    # Docker 환경 등에서 이미 환경변수가 설정되어 있으면 dotenv 불필요
    load_dotenv = None

# .env 로드 (라이브러리가 있고, .env 파일이 존재하는 경우)
if load_dotenv:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_NAME = os.getenv("POSTGRES_DB", "olala")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
# 로컬에서 실행 시 localhost 사용 (docker-compose 외부)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

def main():
    print("Connecting to database...")
    try:
        conn = get_db_connection()
        conn.autocommit = True  # CREATE INDEX often requires autocommit or separate trans
        cur = conn.cursor()

        # docker-compose shm_size를 4GB로 늘렸으므로 그에 맞춰 2GB로 설정
        print("Optimizing session settings: maintenance_work_mem='2GB', max_parallel_maintenance_workers=4, synchronous_commit='off'...")
        cur.execute("SET maintenance_work_mem = '2GB';")
        cur.execute("SET synchronous_commit = 'off';")
        try:
            cur.execute("SET max_parallel_maintenance_workers = 4;")
        except Exception as e:
            print(f"Warning: could not set max_parallel_maintenance_workers: {e}")

        print("Creating HNSW index on wiki_chunks(embedding)... This may take a while.")
        start_time = time.time()
        
        # m=12, ef_construction=48 : 성능과 속도 타협 (기본 16/64보다 빠름)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS wiki_chunks_embedding_idx 
            ON wiki_chunks 
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 12, ef_construction = 48);
        """)
        
        elapsed = time.time() - start_time
        print(f"Index creation completed in {elapsed:.2f} seconds.")

    except Exception as e:
        print(f"Error creating index: {e}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
