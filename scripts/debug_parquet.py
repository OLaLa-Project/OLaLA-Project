import pyarrow.parquet as pq
import os

PARQUET_PATH = "/home/edu09/workspace/slm2/.wiki/new_embeddings_part1.parquet"

if not os.path.exists(PARQUET_PATH):
    print(f"File not found: {PARQUET_PATH}")
else:
    print(f"File exists: {PARQUET_PATH}")
    try:
        table = pq.read_table(PARQUET_PATH)
        print(f"Uncompressed size: {table.nbytes} bytes")
        print(f"Rows: {table.num_rows}")
        print(f"Columns: {table.column_names}")
    except Exception as e:
        print(f"Error details: {e}")
