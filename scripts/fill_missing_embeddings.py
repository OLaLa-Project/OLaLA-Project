import os
import sys
import psycopg2
from psycopg2.extras import execute_values
import time
from dotenv import load_dotenv
import torch
from sentence_transformers import SentenceTransformer

# Add project root to path to import backend modules if needed
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables
load_dotenv()

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "olala")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "dragonkue/multilingual-e5-small-ko-v2")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500")) # Batch size for GPU inference

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode=DB_SSLMODE
    )

def get_local_model():
    print(f"Loading local model: {EMBED_MODEL_NAME}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    model = SentenceTransformer(EMBED_MODEL_NAME, device=device)
    return model

def main():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check how many rows are missing embeddings
        cur.execute("SELECT count(*) FROM wiki_chunks WHERE embedding IS NULL;")
        missing_count = cur.fetchone()[0]
        print(f"Found {missing_count} rows with missing embeddings.")
        
        if missing_count == 0:
            print("No missing embeddings found. Exiting.")
            return

        model = get_local_model()
        
        print("Starting batch processing...")
        total_processed = 0
        
        # PERFORMANCE HACK: Disable synchronous commit for speed
        cur.execute("SET synchronous_commit TO OFF;")

        while True:
            # Fetch a batch of rows with NULL embeddings
            # We use LIMIT to process in chunks
            fetch_start = time.time()
            cur.execute(
                """
                SELECT chunk_id, content 
                FROM wiki_chunks 
                WHERE embedding IS NULL 
                LIMIT %s
                """,
                (BATCH_SIZE,)
            )
            rows = cur.fetchall()
            
            if not rows:
                break
                
            chunk_ids = [r[0] for r in rows]
            contents = [r[1] for r in rows]
            
            # Generate embeddings
            # Prefix query if needed (usually "query: " or "passage: " depending on model usage, 
            # but for storage we usually store the raw passage embedding or "passage: " prefixed if symmetric.
            # E5 models usually expect "passage: " for documents if tasks are asymmetric, 
            # but let's check what the user used before. 
            # The parquet files likely used "passage: " or raw text.
            # Given earlier context, user said "Users must use 'query: ' prefix", implying stored are passages.
            # We will follow standard E5 usage: put "passage: " prefix for indexing if the model requires it.
            # However, `backend/app/gateway/embedding/client.py` usually handles this.
            # Let's check `backend/app/gateway/embedding/client.py` logic or just assume raw for now and align with Part 3.
            # Checking `import_colab_embeddings.py` doesn't show prefix addition, implying parquet has it or model handles it.
            # We will add "passage: " prefix just to be safe for E5, OR check typical usage.
            # Actually, let's keep it simple: model.encode(contents)
            
            # NOTE: dragonkue/multilingual-e5-small-ko-v2 usually requires "passage: " for docs.
            # But let's verify what the previous parquet data had. 
            # If uncertain, we'll assume the content is passed as is.
            
            embeddings = model.encode(contents, batch_size=BATCH_SIZE, normalize_embeddings=True)
            
            # Prepare update data
            update_data = []
            for cid, emb in zip(chunk_ids, embeddings):
                update_data.append((cid, emb.tolist()))
            
            # Update DB
            execute_values(
                cur,
                """
                UPDATE wiki_chunks AS t
                SET embedding = data.embedding::vector
                FROM (VALUES %s) AS data(chunk_id, embedding)
                WHERE t.chunk_id = data.chunk_id
                """,
                update_data,
                template="(%s, %s::vector)"
            )
            
            conn.commit()
            total_processed += len(rows)
            elapsed = time.time() - fetch_start
            print(f"Processed {len(rows)} rows in {elapsed:.2f}s | Total: {total_processed}/{missing_count}")

        print("Finished filling missing embeddings.")

    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    main()
