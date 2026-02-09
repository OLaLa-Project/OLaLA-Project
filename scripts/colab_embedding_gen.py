#!/usr/bin/env python3
"""
Colab GPU에서 위키 청크 임베딩 생성

Input : wiki_chunks.csv (chunk_id, content)
Output: new_embeddings.parquet (chunk_id, embedding)

환경변수(선택):
  INPUT_CSV=wiki_chunks.csv
  OUTPUT_PARQUET=new_embeddings.parquet
  EMBED_MODEL=dragonkue/multilingual-e5-small-ko-v2
  EMBED_DIM=384
  BATCH_SIZE=128
  CSV_CHUNK_SIZE=20000
  NORMALIZE_EMBEDDINGS=true
  PARQUET_COMPRESSION=zstd
"""

import gc
import os

try:
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    import torch
    from sentence_transformers import SentenceTransformer
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Install first: "
        "pip install sentence-transformers pandas pyarrow fastparquet tqdm"
    ) from exc


INPUT_CSV = os.getenv("INPUT_CSV", "wiki_chunks.csv")
OUTPUT_PARQUET = os.getenv("OUTPUT_PARQUET", "new_embeddings.parquet")
MODEL_NAME = os.getenv("EMBED_MODEL", "dragonkue/multilingual-e5-small-ko-v2")
EXPECTED_DIM = int(os.getenv("EMBED_DIM", "384"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "128"))
CSV_CHUNK_SIZE = int(os.getenv("CSV_CHUNK_SIZE", "20000"))
PARQUET_COMPRESSION = os.getenv("PARQUET_COMPRESSION", "zstd")
NORMALIZE_EMBEDDINGS = os.getenv("NORMALIZE_EMBEDDINGS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
}


def _validate_columns(df: pd.DataFrame) -> None:
    required = {"chunk_id", "content"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")


def _read_csv_in_chunks(path: str, chunk_size: int):
    try:
        return pd.read_csv(path, usecols=["chunk_id", "content"], chunksize=chunk_size)
    except ValueError:
        preview = pd.read_csv(path, nrows=5)
        _validate_columns(preview)
        return pd.read_csv(path, chunksize=chunk_size)


def _vector_rows(vectors: np.ndarray) -> list[list[float]]:
    return [row.tolist() for row in vectors]


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"Using device: {device}")
    print(f"Model: {MODEL_NAME}")
    print(f"Expected dim: {EXPECTED_DIM}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"CSV chunk size: {CSV_CHUNK_SIZE}")
    print(f"Normalize embeddings: {NORMALIZE_EMBEDDINGS}")

    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"{INPUT_CSV} not found")

    if os.path.exists(OUTPUT_PARQUET):
        os.remove(OUTPUT_PARQUET)

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME, device=device)

    csv_iter = _read_csv_in_chunks(INPUT_CSV, CSV_CHUNK_SIZE)
    writer = None
    total_rows = 0
    chunk_idx = 0

    for chunk in csv_iter:
        chunk_idx += 1
        _validate_columns(chunk)
        chunk = chunk[["chunk_id", "content"]]

        chunk = chunk.dropna(subset=["content"])
        chunk["chunk_id"] = pd.to_numeric(chunk["chunk_id"], errors="coerce")
        chunk = chunk.dropna(subset=["chunk_id"])

        if chunk.empty:
            print(f"Chunk #{chunk_idx}: skipped (empty)")
            continue

        chunk_ids = chunk["chunk_id"].astype("int64").tolist()
        texts = chunk["content"].astype(str).tolist()

        vectors = model.encode(
            texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=NORMALIZE_EMBEDDINGS,
            convert_to_numpy=True,
        ).astype("float32", copy=False)

        if vectors.ndim != 2:
            raise ValueError(f"Unexpected embedding shape: {vectors.shape}")

        actual_dim = int(vectors.shape[1])
        if actual_dim != EXPECTED_DIM:
            raise ValueError(
                f"Embedding dim mismatch: generated={actual_dim}, expected={EXPECTED_DIM}"
            )

        table = pa.Table.from_arrays(
            [
                pa.array(chunk_ids, type=pa.int64()),
                pa.array(_vector_rows(vectors), type=pa.list_(pa.float32())),
            ],
            names=["chunk_id", "embedding"],
        )

        if writer is None:
            writer = pq.ParquetWriter(
                OUTPUT_PARQUET,
                table.schema,
                compression=PARQUET_COMPRESSION,
            )
        writer.write_table(table)

        total_rows += len(chunk_ids)
        print(f"Chunk #{chunk_idx}: wrote {len(chunk_ids)} rows (total={total_rows})")

        del chunk, chunk_ids, texts, vectors, table
        gc.collect()

    if writer is None:
        raise RuntimeError("No embeddings written. Check input data.")

    writer.close()
    print(f"Done. Saved to {OUTPUT_PARQUET}")
    print(f"Total embeddings: {total_rows}")


if __name__ == "__main__":
    main()
