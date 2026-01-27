import json
import os
import urllib.request
from typing import List


def embed_texts(texts: List[str], *, model: str | None = None, ollama_url: str | None = None, timeout: int = 60) -> List[List[float]]:
    # texts: list of strings -> list of embeddings
    model = model or os.getenv("EMBED_MODEL", "nomic-embed-text")
    ollama_url = (ollama_url or os.getenv("OLLAMA_URL", "http://ollama:11434")).rstrip("/")
    url = f"{ollama_url}/api/embed"

    payload = {"model": model, "input": texts}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        out = json.load(resp)
    return out["embeddings"]


def vec_to_pgvector_literal(vec: List[float], *, ndigits: int = 6) -> str:
    # Returns: [0.123,-0.456,...]
    return "[" + ",".join(f"{x:.{ndigits}f}" for x in vec) + "]"
