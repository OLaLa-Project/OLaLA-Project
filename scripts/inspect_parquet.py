import pyarrow.parquet as pq
import sys

try:
    path = "/home/edu09/workspace/slm2/.wiki/new_embeddings_part1.parquet"
    table = pq.read_table(path)
    print(f"Columns: {table.column_names}")
    print(f"Num rows: {table.num_rows}")
    # Print first row details to see if text exists
    first_row = {col: table[col][0].as_py() for col in table.column_names}
    # Truncate embedding for display
    if 'embedding' in first_row:
        first_row['embedding'] = str(first_row['embedding'])[:50] + "..."
    print(f"First row: {first_row}")
except Exception as e:
    print(f"Error: {e}")
