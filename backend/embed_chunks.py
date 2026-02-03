import os
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
import argparse

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
BATCH_SIZE = 256  # Adjusted for stability

def get_embeddings(texts):
    """Call Ollama Embedding API for a batch of texts."""
    url = f"{OLLAMA_URL}/api/embed"
    try:
        response = requests.post(url, json={
            "model": EMBED_MODEL,
            "input": texts
        }, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data.get("embeddings", [])
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="DB Connection String")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    conn = None
    for i in range(30):
        try:
            conn = psycopg2.connect(args.db)
            conn.autocommit = False
            print("Connected to DB.")
            break
        except Exception as e:
            print(f"Connection failed (retry {i}/30): {e}")
            time.sleep(10)
    
    if not conn:
        print("Could not connect to DB after retries. Exiting.")
        return
    
    total_updated = 0
    start_time = time.time()

    print(f"Starting embedding generation using model '{EMBED_MODEL}'...")

    try:
        while True:
            # 1. Fetch chunks with missing embeddings
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT chunk_id, content 
                    FROM public.wiki_chunks 
                    WHERE embedding IS NULL 
                    LIMIT {args.batch} 
                    FOR UPDATE SKIP LOCKED
                """)
                rows = cur.fetchall()

            if not rows:
                print("No more chunks to process. Done!")
                break

            chunk_ids = [r[0] for r in rows]
            texts = [r[1] for r in rows]

            # 2. Generate Embeddings
            embeddings = get_embeddings(texts)
            
            if not embeddings or len(embeddings) != len(texts):
                print(f"Failed to generate embeddings for batch of {len(texts)}. Retrying...")
                time.sleep(5)
                continue

            # 3. Update DB
            updates = [(emb, cid) for emb, cid in zip(embeddings, chunk_ids)]
            
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    UPDATE public.wiki_chunks AS t 
                    SET embedding = v.embedding::vector 
                    FROM (VALUES %s) AS v(embedding, chunk_id) 
                    WHERE t.chunk_id = v.chunk_id
                    """,
                    updates
                )
            
            conn.commit()
            total_updated += len(rows)
            
            elapsed = time.time() - start_time
            rate = total_updated / elapsed
            print(f"Updated {total_updated} chunks. Rate: {rate:.2f} chunks/sec. Last Batch: {len(rows)}")

    except KeyboardInterrupt:
        print("Stopped by user.")
    except Exception as e:
        conn.rollback()
        print(f"Critical Error: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
