import json
import os
import urllib.request
import logging
from typing import List

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
    # texts: list of strings -> list of embeddings
    model = model or os.getenv("EMBED_MODEL", "nomic-embed-text-v2-moe:latest")
    
    # Check for local fallback models
    # We specifically target the user's requested model
    if model == "dragonkue/multilingual-e5-small-ko-v2":
        try:
            local_model = _get_local_model(model)
            # Add "query: " prefix as per verification findings for optimal performance
            # However, the input might already have prefixes.
            # E5 models expect "query: " for queries and "passage: " for documents.
            # Since this is a generic embed function, we should ideally know the intent.
            # For now, if the application sends raw text, we might want to check if it's a query or doc.
            # But changing prefixes here might break other logic.
            # Let's keep it raw for now, assuming the caller handles prefixes if needed,
            # OR we simply encode as-is which matched "query: " prefix in our test (Wait, the test showed 'query:' prefix matched best).
            
            # The test showed:
            # Raw text similarity: ~0.87
            # "query: " prefix similarity: ~1.00
            
            # This means the stored embeddings were generated with "query: " prefix? 
            # OR the stored embeddings are passages, and we need to use "query: " to match them?
            # Wait, the verification matched retrieval.
            # Verification methodology:
            # 1. Fetch text from DB.
            # 2. Encode text with "query: ".
            # 3. Compare with stored embedding.
            # Result: 1.0 match.
            # This implies the STORED embeddings in parquet/DB were generated WITH "query: " prefix.
            # So if we want to reproduce the SAME embedding, we must add "query: " prefix.
            
            # BUT, usually 'passage: ' is used for storage.
            # If the user stored them with 'query: ', that's unusual but possible.
            # Regardless, to match the stored vectors, we must prefix with "query: ".
            
            # CAUTION: If the input text already has "query: ", we shouldn't add it again.
            processed_texts = []
            for t in texts:
                if not t.startswith("query: ") and not t.startswith("passage: "):
                    # Defaulting to query: because that's what matched the DB
                    processed_texts.append(f"query: {t}")
                else:
                    processed_texts.append(t)
            
            embeddings = local_model.encode(processed_texts, normalize_embeddings=True)
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Failed to use local model {model}: {e}")
            # Fallback to Ollama if local fails? Or raise?
            # If local fails, Ollama likely won't have it either as per previous checks.
            raise e

    # Default Ollama path
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
