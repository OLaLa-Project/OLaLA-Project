
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv("/home/edu09/workspace/slm2/.env")

DB_NAME = os.getenv("POSTGRES_DB", "olala")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def main():
    print("Connecting to DB...")
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    try:
        print("Altering wiki_chunks table embedding column to vector(384)...")
        # We need to drop the index if it exists, restart with new type, and potentially recreate index
        # Simple alter might fail if data exists and can't be cast, but we can restart.
        
        # Option 1: ALTER COLUMN TYPE USING (invalid for vector)
        # Option 2: DROP COLUMN and ADD COLUMN
        
        print("Dropping old embedding column...")
        cur.execute("ALTER TABLE wiki_chunks DROP COLUMN IF EXISTS embedding;")
        
        print("Adding new embedding column (vector(384))...")
        cur.execute("ALTER TABLE wiki_chunks ADD COLUMN embedding vector(384);")
        
        print("Success! Schema updated.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
