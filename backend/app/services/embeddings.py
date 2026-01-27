import os
from typing import List
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))

def embed_text(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    payload = {"model": EMBED_MODEL, "input": texts}  # ALWAYS list
    resp = requests.post(f"{OLLAMA_URL}/api/embed", json=payload, timeout=OLLAMA_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    embs = data["embeddings"]
    if embs and isinstance(embs[0], (int, float)):  # defensive
        embs = [embs]
    return embs
