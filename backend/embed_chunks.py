import os
import signal
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
import argparse
from app.core.settings import settings

# Configuration
OLLAMA_URL = settings.ollama_url
EMBED_MODEL = settings.embed_model
BATCH_SIZE = 8  # Reduced to prevent DB timeouts/crashes
DB_LOCK_TIMEOUT_SECONDS = settings.db_lock_timeout_seconds  # 0 to disable
DB_STATEMENT_TIMEOUT_SECONDS = settings.db_statement_timeout_seconds  # 0 to disable
DB_SYNCHRONOUS_COMMIT = settings.db_synchronous_commit
EMBED_NDIGITS = settings.embed_ndigits
EMBED_STOP_FILE = settings.embed_stop_file

_stop_requested = False


def _handle_stop_signal(signum, frame):
    global _stop_requested
    _stop_requested = True


def vec_to_pgvector_literal(vec, *, ndigits: int = EMBED_NDIGITS) -> str:
    # Returns: [0.123456,-0.654321,...]
    fmt = f"{{:.{ndigits}f}}"
    return "[" + ",".join(fmt.format(float(x)) for x in vec) + "]"

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

def _apply_db_settings(
    conn,
    *,
    lock_timeout_s: float,
    statement_timeout_s: float,
    synchronous_commit: str,
) -> None:
    lock_timeout_ms = int(max(0.0, lock_timeout_s) * 1000)
    statement_timeout_ms = int(max(0.0, statement_timeout_s) * 1000)
    if lock_timeout_ms <= 0 and statement_timeout_ms <= 0 and not synchronous_commit:
        return
    with conn.cursor() as cur:
        if lock_timeout_ms > 0:
            cur.execute("SET lock_timeout = %s;", (f"{lock_timeout_ms}ms",))
        if statement_timeout_ms > 0:
            cur.execute("SET statement_timeout = %s;", (f"{statement_timeout_ms}ms",))
        if synchronous_commit:
            cur.execute("SET synchronous_commit = %s;", (synchronous_commit,))


def get_db_connection(
    db_url,
    *,
    lock_timeout_s: float,
    statement_timeout_s: float,
    synchronous_commit: str,
):
    """Get a fresh DB connection with retry logic."""
    for i in range(5):
        try:
            conn = psycopg2.connect(db_url, connect_timeout=10, application_name="embed_chunks.py")
            _apply_db_settings(
                conn,
                lock_timeout_s=lock_timeout_s,
                statement_timeout_s=statement_timeout_s,
                synchronous_commit=synchronous_commit,
            )
            return conn
        except Exception as e:
            # print(f"DB Connect retry {i}: {e}")
            time.sleep(2)
    raise Exception("Could not connect to DB")

def fetch_batch(conn, batch_size):
    """Fetch and lock a batch of chunks for update."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT chunk_id, content
            FROM public.wiki_chunks
            WHERE embedding IS NULL
            ORDER BY chunk_id
            FOR UPDATE SKIP LOCKED
            LIMIT %s
            """,
            (batch_size,),
        )
        return cur.fetchall()

def update_batch(conn, updates):
    """Update a batch of chunks within the same transaction."""
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            UPDATE public.wiki_chunks AS t
            SET embedding = v.embedding::vector
            FROM (VALUES %s) AS v(embedding, chunk_id)
            WHERE t.chunk_id = v.chunk_id
              AND t.embedding IS NULL
            """,
            updates,
        )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="DB Connection String")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    parser.add_argument("--db-lock-timeout", type=float, default=DB_LOCK_TIMEOUT_SECONDS, help="Seconds to wait on DB locks (0 disables)")
    parser.add_argument("--db-statement-timeout", type=float, default=DB_STATEMENT_TIMEOUT_SECONDS, help="Seconds before canceling a DB statement (0 disables)")
    parser.add_argument("--db-sync-commit", default=DB_SYNCHRONOUS_COMMIT, help="Postgres synchronous_commit setting (e.g., on/off/local)")
    parser.add_argument("--stop-file", default=EMBED_STOP_FILE, help="If this file exists, stop after current step")
    parser.add_argument("--max-batches", type=int, default=0, help="Stop after N batches (0 disables)")
    args = parser.parse_args()

    total_updated = 0
    batches_done = 0
    start_time = time.time()

    signal.signal(signal.SIGINT, _handle_stop_signal)
    signal.signal(signal.SIGTERM, _handle_stop_signal)

    print(f"Starting embedding generation using model '{EMBED_MODEL}'...")
    print(f"DB settings: lock_timeout={args.db_lock_timeout}s, statement_timeout={args.db_statement_timeout}s, synchronous_commit={args.db_sync_commit}")
    if args.stop_file:
        print(f"Stop file: {args.stop_file}")

    try:
        while True:
            if _stop_requested or (args.stop_file and os.path.exists(args.stop_file)):
                print("Stop requested. Exiting before next batch.")
                break

            # 1. Fetch (Connect -> Fetch -> Update -> Commit)
            print("Fetching chunks...")
            conn = get_db_connection(
                args.db,
                lock_timeout_s=args.db_lock_timeout,
                statement_timeout_s=args.db_statement_timeout,
                synchronous_commit=args.db_sync_commit,
            )
            try:
                chunk_batch = fetch_batch(conn, args.batch)
            except Exception as e:
                conn.close()
                print(f"Fetch failed (DB likely busy): {e}. Sleeping...")
                time.sleep(5)
                continue

            if not chunk_batch:
                print("No more chunks to process. Done!")
                conn.close()
                break
                
            print(f"Fetched {len(chunk_batch)} chunks. Sending to Ollama...")

            chunk_ids = [r[0] for r in chunk_batch]
            texts = [r[1] for r in chunk_batch]

            # 2. Embed (No DB connection)
            embeddings = get_embeddings(texts)
            
            if not embeddings or len(embeddings) != len(texts):
                print(f"Failed to generate embeddings. Retrying batch...")
                conn.rollback()
                conn.close()
                time.sleep(5)
                continue

            if _stop_requested or (args.stop_file and os.path.exists(args.stop_file)):
                print("Stop requested. Exiting before DB update.")
                conn.rollback()
                conn.close()
                break

            print("Got embeddings. Updating DB...")

            # 3. Update (Connect -> Update -> Close)
            updates = [(vec_to_pgvector_literal(emb), cid) for emb, cid in zip(embeddings, chunk_ids)]
            
            try:
                t0 = time.time()
                update_batch(conn, updates)
                conn.commit()
                total_updated += len(chunk_batch)
            except Exception as e:
                conn.rollback()
                conn.close()
                print(f"Update failed: {e}. Sleeping...")
                time.sleep(5)
                continue
            conn.close()
            dt = time.time() - t0
            print(f"DB update committed in {dt:.2f}s.")
            
            elapsed = time.time() - start_time
            rate = total_updated / elapsed if elapsed > 0 else 0
            print(f"Updated {total_updated} chunks. Rate: {rate:.2f} chunks/sec. Last Batch: {len(chunk_batch)}")

            batches_done += 1
            if args.max_batches and batches_done >= args.max_batches:
                print(f"Reached max batches ({args.max_batches}). Stopping.")
                break
            
            # Generous sleep for DB recovery
            #time.sleep(2)

    except KeyboardInterrupt:
        print("Stopped by user.")
    except Exception as e:
        print(f"Critical Error: {e}")
        raise

if __name__ == "__main__":
    main()
