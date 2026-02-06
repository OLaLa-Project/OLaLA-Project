import json
import urllib.request
from typing import Any, List, cast

from app.core.settings import settings

def embed_texts(texts: List[str], *, model: str | None = None, ollama_url: str | None = None, timeout: int = 60) -> List[List[float]]:
    # texts: list of strings -> list of embeddings
    model = model or settings.embed_model
    ollama_url = (ollama_url or settings.ollama_url).rstrip("/")
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
    embeddings = out.get("embeddings") if isinstance(out, dict) else None
    if not isinstance(embeddings, list):
        raise ValueError("Embedding response missing 'embeddings' list")
    return cast(List[List[float]], embeddings)


def vec_to_pgvector_literal(vec: List[float], *, ndigits: int = 6) -> str:
    # Returns: [0.123,-0.456,...]
    return "[" + ",".join(f"{x:.{ndigits}f}" for x in vec) + "]"
