import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
import numpy as np
import sys
import os

# Paths
PARQUET_PATH = "/home/edu09/workspace/slm2/.wiki/new_embeddings.parquet"
MODEL_NAME = "dragonkue/multilingual-e5-small-ko-v2"
# MODEL_NAME = "intfloat/multilingual-e5-small" # Fallback to check if it's the base model

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def main():
    print(f"Loading parquet: {PARQUET_PATH}")
    try:
        table = pq.read_table(PARQUET_PATH)
    except Exception as e:
        print(f"Error reading parquet: {e}")
        return

    # Check for text column
    # Common names: "text", "content", "title" + "text", etc.
    # Based on previous file reading, columns are just chunk_id and embedding usually.
    # We need to find the text source. 
    # Let's inspect columns first
    print(f"Columns: {table.column_names}")
    
    # If text column is missing, we can't verify directly unless we have the text.
    # Does the parquet file have text?
    text_col = None
    for col in table.column_names:
        if "text" in col or "content" in col:
            text_col = col
            break
            
    if not text_col:
        print("No text column found in parquet. Cannot verify embedding without source text.")
        # Try to print first row to see if we missed something
        print("First row sample:", {c: table[c][0].as_py() for c in table.column_names if c != 'embedding'})
        return

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # Compare first 3 rows
    for i in range(3):
        text = table[text_col][i].as_py()
        target_embedding = np.array(table['embedding'][i].as_py())
        
        # e5 models often need "query: " or "passage: " prefix
        # We need to check if the user used a prefix.
        # Usually for storage it's "passage: " or no prefix depending on how it was generated.
        
        print(f"\n--- Checking Row {i} ---")
        print(f"Text (first 50 chars): {text[:50]}...")
        
        # Scenario 1: Raw text
        emb1 = model.encode(text)
        sim1 = cosine_similarity(emb1, target_embedding)
        print(f"Similarity (Raw text): {sim1:.4f}")

        # Scenario 2: "passage: " prefix
        emb2 = model.encode(f"passage: {text}")
        sim2 = cosine_similarity(emb2, target_embedding)
        print(f"Similarity ('passage: ' prefix): {sim2:.4f}")

        # Scenario 3: "query: " prefix
        emb3 = model.encode(f"query: {text}")
        sim3 = cosine_similarity(emb3, target_embedding)
        print(f"Similarity ('query: ' prefix): {sim3:.4f}")

        if max(sim1, sim2, sim3) > 0.99:
            print("MATCH CONFIRMED!")
        else:
            print("MISMATCH.")

if __name__ == "__main__":
    main()
