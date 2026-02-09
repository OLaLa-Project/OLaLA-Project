import json
import urllib.request
from typing import Any, List, cast

from app.core.settings import settings

# Hugging Face 임베딩 지원
_hf_model = None

def _get_hf_model():
    """Hugging Face sentence-transformers 모델 로드 (캐시)"""
    global _hf_model
    if _hf_model is None:
        from sentence_transformers import SentenceTransformer
        model_name = settings.embed_model
        print(f"Loading Hugging Face model: {model_name}")
        _hf_model = SentenceTransformer(model_name)
    return _hf_model


def embed_texts(texts: List[str], *, model: str | None = None, ollama_url: str | None = None, timeout: int = 60) -> List[List[float]]:
    """
    텍스트 임베딩 생성
    
    - Hugging Face 모델 (dragonkue/로 시작): sentence-transformers 직접 사용
    - Ollama 모델: Ollama API 호출
    """
    model = model or settings.embed_model
    
    # Hugging Face 모델인지 확인
    if model.startswith("dragonkue/") or "/" in model:
        # Hugging Face sentence-transformers 사용
        hf_model = _get_hf_model()
        embeddings = hf_model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]
    
    # Ollama API 호출
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
