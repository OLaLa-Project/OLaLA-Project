import os
import json
import urllib.request
import logging
from typing import List, cast

from app.core.settings import settings

# Setup logger
logger = logging.getLogger(__name__)

# Global model cache to avoid reloading on every request
_LOCAL_MODEL = None
_LOCAL_MODEL_NAME = None

def _get_local_model(model_name: str):
    global _LOCAL_MODEL, _LOCAL_MODEL_NAME
    if _LOCAL_MODEL is None or _LOCAL_MODEL_NAME != model_name:
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading local embedding model: {model_name} on {device}")
            _LOCAL_MODEL = SentenceTransformer(model_name, device=device)
            _LOCAL_MODEL_NAME = model_name
        except ImportError:
            logger.error("sentence-transformers or torch not installed. Cannot use local model.")
            raise
    return _LOCAL_MODEL

def embed_texts(texts: List[str], *, model: str | None = None, ollama_url: str | None = None, timeout: int = 60) -> List[List[float]]:
    model = model or settings.embed_model
    
    # Check for local fallback models (E5 case)
    if model == "dragonkue/multilingual-e5-small-ko-v2":
        try:
            local_model = _get_local_model(model)
            # E5 models expect "query: " for queries and "passage: " for documents.
            # Stored embeddings matched "query: " prefix.
            processed_texts = []
            for t in texts:
                if not t.startswith("query: ") and not t.startswith("passage: "):
                    processed_texts.append(f"query: {t}")
                else:
                    processed_texts.append(t)
            
            embeddings = local_model.encode(processed_texts, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to use local model {model}: {e}")
            raise e

    # Default Ollama path
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
