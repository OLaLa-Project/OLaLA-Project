import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
import numpy as np
import psycopg2
import os
from dotenv import load_dotenv

# Load env
load_dotenv("/home/edu09/workspace/slm2/.env")

PARQUET_PATH = "/home/edu09/workspace/slm2/.wiki/new_embeddings.parquet"
MODEL_NAME = "dragonkue/multilingual-e5-small-ko-v2"

# DB Config
DB_NAME = os.getenv("POSTGRES_DB", "olala")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
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

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def main():
    print(f"Loading parquet: {PARQUET_PATH}")
    try:
        table = pq.read_table(PARQUET_PATH)
    except Exception as e:
        print(f"Error reading parquet: {e}")
        return

    # Get sample chunk_ids
    sample_indices = [0, 100, 1000] # Random indices
    samples = []
    
    for idx in sample_indices:
        if idx < table.num_rows:
            chunk_id = table['chunk_id'][idx].as_py()
            embedding = np.array(table['embedding'][idx].as_py())
            samples.append((chunk_id, embedding))
            
    if not samples:
        print("No samples found.")
        return
        
    print(f"Connecting to DB to fetch text for {len(samples)} samples...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    
    for chunk_id, target_embedding in samples:
        # Fetch text
        # Assuming table name is wiki_chunks and column is chunk_content or similar.
        # Let's try to inspect columns if query fails.
        # But standard is usually 'chunk_id', 'text', 'title', etc.
        # Based on previous file reading of import script, target table is 'wiki_chunks'.
        # Key col is 'chunk_id'.
        # We need to find the text column. Usually 'text' or 'content'.
        
        # First, let's check columns of wiki_chunks
        cur.execute("SELECT * FROM wiki_chunks LIMIT 1")
        col_names = [desc[0] for desc in cur.description]
        # Identify text column
        text_col = 'text' if 'text' in col_names else ('content' if 'content' in col_names else None)
        
        if not text_col:
            print(f"Could not identify text column in {col_names}")
            break
            
        cur.execute(f"SELECT {text_col} FROM wiki_chunks WHERE chunk_id = %s", (chunk_id,))
        row = cur.fetchone()
        
        if not row:
            print(f"Chunk {chunk_id} not found in DB.")
            continue
            
        text = row[0]
        print(f"\n--- Checking Chunk {chunk_id} ---")
        print(f"Text (first 50 chars): {text[:50]}...")
        
        # Calculate similarity
        # Scenario 1: Raw text
        emb1 = model.encode(text)
        sim1 = cosine_similarity(emb1, target_embedding)
        print(f"Similarity (Raw): {sim1:.4f}")

        # Scenario 2: "passage: " prefix
        emb2 = model.encode(f"passage: {text}")
        sim2 = cosine_similarity(emb2, target_embedding)
        print(f"Similarity ('passage: '): {sim2:.4f}")

        # Scenario 3: "query: " prefix
        emb3 = model.encode(f"query: {text}")
        sim3 = cosine_similarity(emb3, target_embedding)
        print(f"Similarity ('query: '): {sim3:.4f}")
        
        if max(sim1, sim2, sim3) > 0.99:
             print("MATCH CONFIRMED!")
        else:
             print("MISMATCH.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
