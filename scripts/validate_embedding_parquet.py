#!/usr/bin/env python3
"""
Validate embedding parquet integrity and optional DB chunk_id match.

Usage example:
  python scripts/validate_embedding_parquet.py \
    --input .wiki/new_embeddings_part3.parquet \
    --embed-dim 384 \
    --db-check
"""

import argparse
import os
from typing import Iterable

import numpy as np
import pyarrow.parquet as pq

try:
    import psycopg2
    from psycopg2.extras import execute_values
except Exception:
    psycopg2 = None
    execute_values = None


DEFAULT_INPUT_EMBED_CANDIDATES = ("embedding", "element", "vector", "emb")


def _resolve_embed_col(names: set[str], preferred: str | None) -> str:
    if preferred:
        if preferred not in names:
            raise ValueError(f"embed column '{preferred}' not found; available={sorted(names)}")
        return preferred
    for c in DEFAULT_INPUT_EMBED_CANDIDATES:
        if c in names:
            return c
    raise ValueError(f"embedding column not found; available={sorted(names)}")


def _chunks(values: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


def validate_parquet(path: str, embed_dim: int, preferred_col: str | None, batch_size: int) -> dict[str, int]:
    pf = pq.ParquetFile(path)
    top_cols = set(pf.schema_arrow.names)
    if "chunk_id" not in top_cols:
        raise ValueError(f"'chunk_id' not in parquet columns: {sorted(top_cols)}")
    embed_col = _resolve_embed_col(top_cols, preferred_col)

    seen: set[int] = set()
    total_rows = 0
    duplicate_rows = 0
    none_embedding_rows = 0
    invalid_dim_rows = 0
    non_finite_rows = 0

    for batch in pf.iter_batches(batch_size=batch_size, columns=["chunk_id", embed_col]):
        ids = batch.column(0).to_pylist()
        embs = batch.column(1).to_pylist()

        valid_indices: list[int] = []
        for idx, (cid, emb) in enumerate(zip(ids, embs)):
            if cid is None:
                continue

            cid_int = int(cid)
            total_rows += 1

            if cid_int in seen:
                duplicate_rows += 1
            else:
                seen.add(cid_int)

            if emb is None:
                none_embedding_rows += 1
                continue

            if len(emb) != embed_dim:
                invalid_dim_rows += 1
                continue

            valid_indices.append(idx)

        if not valid_indices:
            continue

        arr = np.asarray([embs[i] for i in valid_indices], dtype=np.float32)
        finite_mask = np.isfinite(arr).all(axis=1)
        non_finite_rows += int((~finite_mask).sum())

    return {
        "parquet_rows_meta": int(pf.metadata.num_rows if pf.metadata else 0),
        "total_rows_scanned": total_rows,
        "unique_chunk_ids": len(seen),
        "duplicate_rows": duplicate_rows,
        "none_embedding_rows": none_embedding_rows,
        "invalid_dim_rows": invalid_dim_rows,
        "non_finite_rows": non_finite_rows,
        "embed_col": embed_col,  # type: ignore[typeddict-item]
        "ids": seen,  # type: ignore[typeddict-item]
    }


def validate_db(ids: set[int], *, db_host: str, db_port: int, db_name: str, db_user: str, db_password: str, sslmode: str) -> dict[str, int]:
    if psycopg2 is None or execute_values is None:
        raise RuntimeError("psycopg2 is required for --db-check")

    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        sslmode=sslmode,
    )
    cur = conn.cursor()
    try:
        cur.execute("CREATE TEMP TABLE tmp_validate_ids (chunk_id BIGINT PRIMARY KEY) ON COMMIT DROP;")
        id_list = list(ids)
        for chunk in _chunks(id_list, 10000):
            execute_values(
                cur,
                "INSERT INTO tmp_validate_ids (chunk_id) VALUES %s ON CONFLICT DO NOTHING",
                [(x,) for x in chunk],
                page_size=10000,
            )

        cur.execute("SELECT COUNT(*) FROM tmp_validate_ids")
        (tmp_ids_count,) = cur.fetchone()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM tmp_validate_ids t
            LEFT JOIN wiki_chunks w ON w.chunk_id = t.chunk_id
            WHERE w.chunk_id IS NULL
            """
        )
        (not_found_in_db,) = cur.fetchone()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM tmp_validate_ids t
            JOIN wiki_chunks w ON w.chunk_id = t.chunk_id
            WHERE w.embedding IS NOT NULL
            """
        )
        (already_embedded_in_db,) = cur.fetchone()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM tmp_validate_ids t
            JOIN wiki_chunks w ON w.chunk_id = t.chunk_id
            WHERE w.embedding IS NULL
            """
        )
        (missing_embedding_in_db,) = cur.fetchone()

        cur.execute("SELECT COUNT(*) FROM wiki_chunks")
        (total_db_rows,) = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM wiki_chunks WHERE embedding IS NULL")
        (db_remaining_before_import,) = cur.fetchone()

        conn.commit()
        return {
            "tmp_ids_count": int(tmp_ids_count),
            "not_found_in_db": int(not_found_in_db),
            "already_embedded_in_db": int(already_embedded_in_db),
            "missing_embedding_in_db": int(missing_embedding_in_db),
            "total_db_rows": int(total_db_rows),
            "db_remaining_before_import": int(db_remaining_before_import),
        }
    finally:
        cur.close()
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate embedding parquet before DB import")
    parser.add_argument("--input", required=True, help="path to parquet file")
    parser.add_argument("--embed-dim", type=int, default=int(os.getenv("EMBED_DIM", "384")))
    parser.add_argument("--embed-col", default=os.getenv("INPUT_EMBED_COLUMN", "").strip() or None)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--db-check", action="store_true")
    args = parser.parse_args()

    pstats = validate_parquet(args.input, args.embed_dim, args.embed_col, args.batch_size)
    ids = pstats.pop("ids")
    print("PARQUET_VALIDATION")
    for k, v in pstats.items():
        print(f"  {k}={v}")

    if args.db_check:
        db_stats = validate_db(
            ids,
            db_host=os.getenv("COLAB_IMPORT_DB_HOST", os.getenv("DB_HOST", "localhost")),
            db_port=int(os.getenv("COLAB_IMPORT_DB_PORT", os.getenv("DB_PORT", "5432"))),
            db_name=os.getenv("POSTGRES_DB", "olala"),
            db_user=os.getenv("POSTGRES_USER", "postgres"),
            db_password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            sslmode=os.getenv("COLAB_IMPORT_DB_SSLMODE", os.getenv("DB_SSLMODE", "disable")),
        )
        print("DB_MATCH")
        for k, v in db_stats.items():
            print(f"  {k}={v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
