#!/bin/bash
IMPORT_PID=84047

echo "Waiting for import process (PID $IMPORT_PID) to finish..."
while ps -p $IMPORT_PID > /dev/null; do
    sleep 5
done

echo "Import finished. Starting fill_missing_embeddings.py..."
/home/edu09/workspace/slm2/.venv/bin/python /home/edu09/workspace/slm2/scripts/fill_missing_embeddings.py
