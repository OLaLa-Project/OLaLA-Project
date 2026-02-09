#!/usr/bin/env python3
"""
로컬 Postgres에서 Colab 임베딩용 CSV 추출

기본 출력 컬럼: chunk_id, content
기본 조건: embedding IS NULL

환경변수(선택):
  OUTPUT_CSV=wiki_chunks.csv
  POSTGRES_DB=olala
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=postgres
  EXPORT_DB_HOST=localhost
  EXPORT_DB_PORT=5432
  EXPORT_DB_SSLMODE=prefer

  EXPORT_TABLE=wiki_chunks
  EXPORT_KEY_COLUMN=chunk_id
  EXPORT_TEXT_COLUMN=content
  EXPORT_EMBED_COLUMN=embedding
  EXPORT_ONLY_MISSING=true
"""

import os
import re

import psycopg2

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_NAME = os.getenv("POSTGRES_DB", "olala")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.getenv("EXPORT_DB_HOST", os.getenv("DB_HOST", "localhost"))
DB_PORT = os.getenv("EXPORT_DB_PORT", os.getenv("DB_PORT", "5432"))
DB_SSLMODE = os.getenv("EXPORT_DB_SSLMODE", os.getenv("DB_SSLMODE", "prefer"))

OUTPUT_CSV = os.getenv("OUTPUT_CSV", "wiki_chunks.csv")
EXPORT_TABLE = os.getenv("EXPORT_TABLE", "wiki_chunks")
EXPORT_KEY_COLUMN = os.getenv("EXPORT_KEY_COLUMN", "chunk_id")
EXPORT_TEXT_COLUMN = os.getenv("EXPORT_TEXT_COLUMN", "content")
EXPORT_EMBED_COLUMN = os.getenv("EXPORT_EMBED_COLUMN", "embedding")
EXPORT_ONLY_MISSING = os.getenv("EXPORT_ONLY_MISSING", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str, label: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier for {label}: {name}")
    return name


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


def main() -> None:
    table_name = _validate_identifier(EXPORT_TABLE, "EXPORT_TABLE")
    key_col = _validate_identifier(EXPORT_KEY_COLUMN, "EXPORT_KEY_COLUMN")
    text_col = _validate_identifier(EXPORT_TEXT_COLUMN, "EXPORT_TEXT_COLUMN")
    emb_col = _validate_identifier(EXPORT_EMBED_COLUMN, "EXPORT_EMBED_COLUMN")

    where_clause = f"{emb_col} IS NULL" if EXPORT_ONLY_MISSING else "TRUE"

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        count_sql = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause};"
        cur.execute(count_sql)
        total = int(cur.fetchone()[0])
        print(f"Rows to export: {total}")

        copy_sql = f"""
        COPY (
            SELECT {key_col}, {text_col}
            FROM {table_name}
            WHERE {where_clause}
            ORDER BY {key_col}
        ) TO STDOUT WITH CSV HEADER
        """

        with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
            cur.copy_expert(copy_sql, f)

        print(f"Exported CSV: {OUTPUT_CSV}")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
