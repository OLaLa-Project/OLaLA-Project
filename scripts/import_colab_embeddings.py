#!/usr/bin/env python3
"""
Colab에서 생성한 Parquet 임베딩을 Postgres(pgvector)로 반영

기본 시나리오:
  1) Colab: new_embeddings.parquet 생성
  2) 로컬: 이 스크립트 실행하여 DB 업데이트

환경변수(선택):
  INPUT_PARQUET=new_embeddings.parquet
  EMBED_DIM=384
  BATCH_SIZE=5000

  # DB 연결
  POSTGRES_DB=olala
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=postgres
  COLAB_IMPORT_DB_HOST=localhost
  COLAB_IMPORT_DB_PORT=5432
  COLAB_IMPORT_DB_SSLMODE=prefer

  # 대상 테이블
  COLAB_IMPORT_TABLE=wiki_chunks
  COLAB_IMPORT_KEY_COLUMN=chunk_id
  COLAB_IMPORT_EMBED_COLUMN=embedding
"""

import os
import re
import time

try:
    import numpy as np
    import psycopg2
    import pyarrow.parquet as pq
    from psycopg2.extras import execute_values
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Install first: "
        "pip install numpy psycopg2-binary python-dotenv pyarrow"
    ) from exc

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_NAME = os.getenv("POSTGRES_DB", "olala")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.getenv("COLAB_IMPORT_DB_HOST", os.getenv("DB_HOST", "localhost"))
DB_PORT = os.getenv("COLAB_IMPORT_DB_PORT", os.getenv("DB_PORT", "5432"))
DB_SSLMODE = os.getenv("COLAB_IMPORT_DB_SSLMODE", os.getenv("DB_SSLMODE", "prefer"))

INPUT_PARQUET = os.getenv("INPUT_PARQUET", "new_embeddings.parquet")
TARGET_TABLE = os.getenv("COLAB_IMPORT_TABLE", "wiki_chunks")
TARGET_KEY_COLUMN = os.getenv("COLAB_IMPORT_KEY_COLUMN", "chunk_id")
TARGET_EMBED_COLUMN = os.getenv("COLAB_IMPORT_EMBED_COLUMN", "embedding")
INPUT_EMBED_COLUMN = os.getenv("INPUT_EMBED_COLUMN", "").strip()

EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DEFAULT_INPUT_EMBED_CANDIDATES = ("embedding", "element", "vector", "emb")


def _validate_identifier(name: str, label: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier for {label}: {name}")
    return name


def _vector_literal(raw_embedding: object) -> str:
    if isinstance(raw_embedding, np.ndarray):
        values = raw_embedding.tolist()
    else:
        values = list(raw_embedding)

    if len(values) != EMBED_DIM:
        raise ValueError(f"Embedding dim mismatch in row: {len(values)} != {EMBED_DIM}")

    return "[" + ",".join(f"{float(v):.8f}" for v in values) + "]"


def get_db_connection():
    kwargs = {
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "host": DB_HOST,
        "port": DB_PORT,
    }
    if DB_SSLMODE:
        kwargs["sslmode"] = DB_SSLMODE
    return psycopg2.connect(**kwargs)


def _fetch_column_type(cur, table_name: str, column_name: str) -> str | None:
    cur.execute(
        """
        SELECT format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = %s
          AND a.attname = %s
          AND a.attnum > 0
          AND NOT a.attisdropped
        LIMIT 1;
        """,
        (table_name, column_name),
    )
    row = cur.fetchone()
    return None if row is None else str(row[0])


def _resolve_input_embed_column(names: set[str]) -> str:
    if INPUT_EMBED_COLUMN:
        if INPUT_EMBED_COLUMN not in names:
            raise ValueError(
                f"INPUT_EMBED_COLUMN='{INPUT_EMBED_COLUMN}' not found. "
                f"Available columns: {sorted(names)}"
            )
        return INPUT_EMBED_COLUMN
    for candidate in _DEFAULT_INPUT_EMBED_CANDIDATES:
        if candidate in names:
            return candidate
    raise ValueError(
        "Could not find embedding column. "
        f"Tried {_DEFAULT_INPUT_EMBED_CANDIDATES}, available={sorted(names)}"
    )


def _open_parquet(path: str) -> tuple[pq.ParquetFile, str]:
    parquet_file = pq.ParquetFile(path)
    # Use top-level Arrow columns. parquet schema.names can include nested child names (e.g. "element").
    names = set(parquet_file.schema_arrow.names)
    if "chunk_id" not in names:
        raise ValueError(f"Parquet must include columns: ['chunk_id']; available={sorted(names)}")
    input_embed_col = _resolve_input_embed_column(names)
    return parquet_file, input_embed_col


def _detect_parquet_dim(parquet_file: pq.ParquetFile, input_embed_col: str) -> int:
    for batch in parquet_file.iter_batches(batch_size=1024, columns=[input_embed_col]):
        for emb in batch.column(0).to_pylist():
            if emb is None:
                continue
            values = emb.tolist() if isinstance(emb, np.ndarray) else list(emb)
            return len(values)
    return 0


def _iter_rows(parquet_file: pq.ParquetFile, batch_size: int, input_embed_col: str):
    for batch in parquet_file.iter_batches(
        batch_size=batch_size,
        columns=["chunk_id", input_embed_col],
    ):
        chunk_ids = batch.column(0).to_pylist()
        embeddings = batch.column(1).to_pylist()
        rows = []

        for chunk_id, emb in zip(chunk_ids, embeddings):
            if chunk_id is None or emb is None:
                continue
            rows.append((int(chunk_id), _vector_literal(emb)))

        if rows:
            yield rows


def main() -> None:
    table_name = _validate_identifier(TARGET_TABLE, "COLAB_IMPORT_TABLE")
    key_col = _validate_identifier(TARGET_KEY_COLUMN, "COLAB_IMPORT_KEY_COLUMN")
    embed_col = _validate_identifier(TARGET_EMBED_COLUMN, "COLAB_IMPORT_EMBED_COLUMN")

    if not os.path.exists(INPUT_PARQUET):
        raise FileNotFoundError(f"{INPUT_PARQUET} not found")

    parquet_file, input_embed_col = _open_parquet(INPUT_PARQUET)
    parquet_rows = parquet_file.metadata.num_rows if parquet_file.metadata else 0
    print(f"Parquet rows (metadata): {parquet_rows}")
    print(f"Input embedding column: {input_embed_col}")

    sample_dim = _detect_parquet_dim(parquet_file, input_embed_col)
    if sample_dim == 0:
        print("No valid embedding row found in parquet. Exiting.")
        return

    if sample_dim != EMBED_DIM:
        raise ValueError(
            f"Embedding dim mismatch: parquet={sample_dim}, EMBED_DIM={EMBED_DIM}. "
            "Please align model and EMBED_DIM."
        )

    conn = get_db_connection()
    cur = conn.cursor()

    print(f"Connecting DB: host={DB_HOST} port={DB_PORT} db={DB_NAME} sslmode={DB_SSLMODE}")
    print(f"Target table: {table_name} (key={key_col}, embed={embed_col})")

    try:
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
        except Exception as ext_err:
            print(f"Warning: could not ensure pgvector extension: {ext_err}")
            conn.rollback()

        key_type = _fetch_column_type(cur, table_name, key_col)
        embed_type = _fetch_column_type(cur, table_name, embed_col)
        if key_type is None:
            raise ValueError(f"Column not found: {table_name}.{key_col}")
        if embed_type is None:
            raise ValueError(f"Column not found: {table_name}.{embed_col}")

        dim_match = re.search(r"vector\((\d+)\)", embed_type)
        if dim_match:
            db_dim = int(dim_match.group(1))
            if db_dim != EMBED_DIM:
                raise ValueError(
                    f"DB vector dim mismatch: db={db_dim}, EMBED_DIM={EMBED_DIM}"
                )

        print("Creating temporary table...")
        cur.execute(
            f"""
            CREATE TEMP TABLE temp_embeddings (
                chunk_id BIGINT,
                embedding vector({EMBED_DIM})
            ) ON COMMIT DROP;
            """
        )

        inserted_rows = 0
        insert_started_at = time.time()

        print("Inserting into temporary table...")
        for rows in _iter_rows(parquet_file, BATCH_SIZE, input_embed_col):
            execute_values(
                cur,
                "INSERT INTO temp_embeddings (chunk_id, embedding) VALUES %s",
                rows,
                template="(%s, %s::vector)",
                page_size=min(1000, len(rows)),
            )

            inserted_rows += len(rows)
            print(f"  Inserted {inserted_rows} rows")

        print(f"Temp insert completed in {time.time() - insert_started_at:.2f}s")

        print(f"Updating {table_name}...")
        update_started_at = time.time()
        cur.execute(
            f"""
            UPDATE {table_name} AS t
            SET {embed_col} = e.embedding
            FROM temp_embeddings AS e
            WHERE t.{key_col} = e.chunk_id;
            """
        )
        affected_rows = cur.rowcount
        conn.commit()

        print(f"Update completed in {time.time() - update_started_at:.2f}s")
        print(f"Updated rows: {affected_rows}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
