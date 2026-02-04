import os
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
import argparse

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
BATCH_SIZE = 32  # Reduced from 256 for debugging/stability

def get_embeddings(texts):
    """Call Ollama Embedding API for a batch of texts."""
    url = f"{OLLAMA_URL}/api/embed"
    try:
        # print(f"Sending batch of {len(texts)} to Ollama...")
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

def get_db_connection(db_url):
    """Get a fresh DB connection with retry logic."""
    for i in range(5):
        try:
            conn = psycopg2.connect(db_url, connect_timeout=10)
            return conn
        except Exception as e:
            # print(f"DB Connect retry {i}: {e}")
            time.sleep(2)
    raise Exception("Could not connect to DB")

def fetch_batch(db_url, batch_size):
    """Fetch a batch of chunks separately."""
    conn = get_db_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT chunk_id, content 
                FROM public.wiki_chunks 
                WHERE embedding IS NULL 
                LIMIT {batch_size}
            """)
            return cur.fetchall()
    finally:
        conn.close()

def update_batch(db_url, updates):
    """Update a batch of chunks separately."""
    conn = get_db_connection(db_url)
    try:
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
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="DB Connection String")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    total_updated = 0
    start_time = time.time()

    print(f"Starting embedding generation using model '{EMBED_MODEL}'...")

    try:
        while True:
            # 1. Fetch (Connect -> Fetch -> Close)
            print("Fetching chunks...")
            try:
                chunk_batch = fetch_batch(args.db, args.batch)
            except Exception as e:
                print(f"Fetch failed (DB likely busy): {e}. Sleeping...")
                time.sleep(5)
                continue

            if not chunk_batch:
                print("No more chunks to process. Done!")
                break
                
            print(f"Fetched {len(chunk_batch)} chunks. Sending to Ollama...")

            chunk_ids = [r[0] for r in chunk_batch]
            texts = [r[1] for r in chunk_batch]

            # 2. Embed (No DB connection)
            embeddings = get_embeddings(texts)
            
            if not embeddings or len(embeddings) != len(texts):
                print(f"Failed to generate embeddings. Retrying batch...")
                time.sleep(5)
                continue

            print("Got embeddings. Updating DB...")

            # 3. Update (Connect -> Update -> Close)
            updates = [(emb, cid) for emb, cid in zip(embeddings, chunk_ids)]
            
            try:
                update_batch(args.db, updates)
                total_updated += len(chunk_batch)
            except Exception as e:
                print(f"Update failed: {e}. Sleeping...")
                time.sleep(5)
                continue
            
            elapsed = time.time() - start_time
            rate = total_updated / elapsed if elapsed > 0 else 0
            print(f"Updated {total_updated} chunks. Rate: {rate:.2f} chunks/sec. Last Batch: {len(chunk_batch)}")
            
            # Generous sleep for DB recovery
            time.sleep(2.0)

    except KeyboardInterrupt:
        print("Stopped by user.")
    except Exception as e:
        print(f"Critical Error: {e}")
        raise

if __name__ == "__main__":
    main()
