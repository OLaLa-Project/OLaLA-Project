from __future__ import annotations

import app.services.wiki_usecase as wiki_usecase


class _VectorOnlyRepo:
    def __init__(self):
        self.fallback_calls = 0
        self.vector_candidate_calls = 0
        self.fts_score_calls = 0

    def vector_search_candidates(self, _qvec_literal: str, limit: int = 50):  # noqa: ARG002
        self.vector_candidate_calls += 1
        return [(101, "테스트 문서")]

    def vector_search(self, _qvec_literal: str, top_k: int = 10, page_ids=None):  # noqa: ARG002
        return [
            {
                "title": "테스트 문서",
                "page_id": 101,
                "chunk_id": 9001,
                "chunk_idx": 0,
                "content": "테스트 위키 본문",
                "dist": 0.2,
                "lex_score": 0.0,
            }
        ]

    def find_chunks_by_fts_fallback(self, query: str, limit: int = 10):  # noqa: ARG002
        self.fallback_calls += 1
        return []

    def calculate_fts_scores_for_chunks(self, chunk_ids, query: str):  # noqa: ARG002
        self.fts_score_calls += 1
        return {int(chunk_id): 0.0 for chunk_id in chunk_ids}

    def fetch_window(self, page_id: int, start_idx: int, end_idx: int):  # noqa: ARG002
        return ["테스트 위키 본문"]

    def find_pages_by_any_keyword(self, keywords, limit: int = 50):  # noqa: ARG002
        return []

    def find_candidates_by_chunk_fts(self, query: str, limit: int = 50):  # noqa: ARG002
        return []


def test_retrieve_wiki_hits_vector_mode_disables_fts_fallback(monkeypatch):
    repo = _VectorOnlyRepo()
    monkeypatch.setattr(wiki_usecase, "WikiRepository", lambda _db: repo)
    monkeypatch.setattr(wiki_usecase.settings, "stage3_wiki_strict_vector_only", True)
    monkeypatch.setattr(wiki_usecase, "embed_texts", lambda _texts: [[0.1, 0.2, 0.3]])
    monkeypatch.setattr(wiki_usecase, "vec_to_pgvector_literal", lambda _vec: "[0.1,0.2,0.3]")

    out = wiki_usecase.retrieve_wiki_hits(
        db=object(),  # type: ignore[arg-type]
        question="테스트 질문",
        top_k=1,
        window=0,
        page_limit=5,
        search_mode="vector",
    )

    assert out["debug"]["vector_only"] is True
    assert out["debug"]["direct_vector_fastpath"] is True
    assert out["debug"]["vector_db_calls"] == 1
    assert repo.vector_candidate_calls == 0
    assert repo.fts_score_calls == 0
    assert repo.fallback_calls == 0
    assert len(out["hits"]) == 1


def test_retrieve_wiki_hits_vector_mode_returns_empty_when_embedding_fails(monkeypatch):
    repo = _VectorOnlyRepo()
    monkeypatch.setattr(wiki_usecase, "WikiRepository", lambda _db: repo)
    monkeypatch.setattr(wiki_usecase.settings, "stage3_wiki_strict_vector_only", True)

    def _raise_embed(_texts):
        raise RuntimeError("embed unavailable")

    monkeypatch.setattr(wiki_usecase, "embed_texts", _raise_embed)

    out = wiki_usecase.retrieve_wiki_hits(
        db=object(),  # type: ignore[arg-type]
        question="테스트 질문",
        top_k=2,
        window=0,
        page_limit=5,
        search_mode="vector",
    )

    assert out["debug"]["vector_only"] is True
    assert "embed unavailable" in str(out["debug"].get("embed_error"))
    assert repo.vector_candidate_calls == 0
    assert out["hits"] == []


def test_retrieve_wiki_hits_uses_wiki_query_embed_backend_and_model(monkeypatch):
    repo = _VectorOnlyRepo()
    monkeypatch.setattr(wiki_usecase, "WikiRepository", lambda _db: repo)
    monkeypatch.setattr(wiki_usecase.settings, "stage3_wiki_strict_vector_only", True)
    monkeypatch.setattr(wiki_usecase.settings, "wiki_query_embed_backend", "ollama")
    monkeypatch.setattr(wiki_usecase.settings, "wiki_query_embed_model", "nomic-embed-text")

    captured: dict[str, object] = {}

    def _fake_embed(texts, *, model=None, backend=None, **kwargs):  # noqa: ANN001, ANN003
        captured["texts"] = list(texts)
        captured["model"] = model
        captured["backend"] = backend
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr(wiki_usecase, "embed_texts", _fake_embed)
    monkeypatch.setattr(wiki_usecase, "vec_to_pgvector_literal", lambda _vec: "[0.1,0.2,0.3]")

    out = wiki_usecase.retrieve_wiki_hits(
        db=object(),  # type: ignore[arg-type]
        question="테스트 질문",
        top_k=1,
        window=0,
        page_limit=5,
        search_mode="vector",
    )

    assert captured["texts"] == ["테스트 질문"]
    assert captured["model"] == "nomic-embed-text"
    assert captured["backend"] == "ollama"
    assert out["debug"]["query_embed_backend"] == "ollama"
    assert out["debug"]["query_embed_model"] == "nomic-embed-text"


def test_retrieve_wiki_hits_falls_back_to_embed_model_when_wiki_model_empty(monkeypatch):
    repo = _VectorOnlyRepo()
    monkeypatch.setattr(wiki_usecase, "WikiRepository", lambda _db: repo)
    monkeypatch.setattr(wiki_usecase.settings, "stage3_wiki_strict_vector_only", True)
    monkeypatch.setattr(wiki_usecase.settings, "wiki_query_embed_backend", "auto")
    monkeypatch.setattr(wiki_usecase.settings, "wiki_query_embed_model", "")
    monkeypatch.setattr(wiki_usecase.settings, "embed_model", "dragonkue/multilingual-e5-small-ko-v2")

    captured: dict[str, object] = {}

    def _fake_embed(texts, *, model=None, backend=None, **kwargs):  # noqa: ANN001, ANN003
        captured["texts"] = list(texts)
        captured["model"] = model
        captured["backend"] = backend
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr(wiki_usecase, "embed_texts", _fake_embed)
    monkeypatch.setattr(wiki_usecase, "vec_to_pgvector_literal", lambda _vec: "[0.1,0.2,0.3]")

    out = wiki_usecase.retrieve_wiki_hits(
        db=object(),  # type: ignore[arg-type]
        question="테스트 질문",
        top_k=1,
        window=0,
        page_limit=5,
        search_mode="vector",
    )

    assert captured["texts"] == ["테스트 질문"]
    assert captured["model"] == "dragonkue/multilingual-e5-small-ko-v2"
    assert captured["backend"] == "auto"
    assert out["debug"]["query_embed_backend"] == "auto"
    assert out["debug"]["query_embed_model"] == "dragonkue/multilingual-e5-small-ko-v2"
