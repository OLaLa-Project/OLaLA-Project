import json
import urllib.request
from typing import Any, List, cast

from app.core.settings import settings

# Hugging Face 임베딩 지원
_hf_models: dict[str, Any] = {}


def _is_hf_model_name(model_name: str) -> bool:
    normalized = str(model_name or "").strip()
    return "/" in normalized


def _resolve_embed_backend(model_name: str, backend: str | None) -> str:
    requested = str(backend or "auto").strip().lower() or "auto"
    if requested not in {"auto", "ollama", "hf"}:
        requested = "auto"
    if requested == "auto":
        return "hf" if _is_hf_model_name(model_name) else "ollama"
    return requested


def _get_hf_model(model_name: str):
    """Hugging Face sentence-transformers 모델 로드 (캐시)"""
    cached = _hf_models.get(model_name)
    if cached is None:
        from sentence_transformers import SentenceTransformer
        print(f"Loading Hugging Face model: {model_name}")
        cached = SentenceTransformer(model_name)
        _hf_models[model_name] = cached
    return cached


def embed_texts(
    texts: List[str],
    *,
    model: str | None = None,
    ollama_url: str | None = None,
    timeout: int = 60,
    backend: str | None = None,
) -> List[List[float]]:
    """
    텍스트 임베딩 생성

    - Hugging Face 모델: sentence-transformers 직접 사용
    - Ollama 모델: Ollama API 호출
    - backend='ollama'면 model 이름과 무관하게 Ollama를 강제 사용
    """
    model_name = str(model or settings.embed_model).strip()
    resolved_backend = _resolve_embed_backend(model_name, backend)

    if resolved_backend == "hf":
        # Hugging Face sentence-transformers 사용
        hf_model = _get_hf_model(model_name)
        embeddings = hf_model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    # Ollama API 호출
    ollama_url = str(ollama_url or settings.ollama_url).rstrip("/")
    url = f"{ollama_url}/api/embed"

    payload = {"model": model_name, "input": texts}
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
