import psycopg2
import os
import time
from dotenv import load_dotenv

def get_db_connection():
    load_dotenv()
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "olala"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def main():
    print("Connecting to database...")
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cur = conn.cursor()

        print("Optimizing session settings for GIN index creation...")
        cur.execute("SET maintenance_work_mem = '2GB';")
        cur.execute("SET synchronous_commit = 'off';")
        try:
            cur.execute("SET max_parallel_maintenance_workers = 4;")
        except Exception as e:
            print(f"Warning: could not set max_parallel_maintenance_workers: {e}")

        print("Creating GIN index on wiki_chunks(content) for FTS... This may take a few minutes.")
        start_time = time.time()
        
        # Using 'simple' config to match repository logic
        cur.execute("""
            CREATE INDEX IF NOT EXISTS wiki_chunks_content_fts_idx 
            ON wiki_chunks 
            USING gin (to_tsvector('simple', content));
        """)
        
        elapsed = time.time() - start_time
        print(f"GIN Index creation completed in {elapsed:.2f} seconds.")

    except Exception as e:
        print(f"Error creating GIN index: {e}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
