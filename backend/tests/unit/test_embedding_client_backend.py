from __future__ import annotations

import io
import json

import app.orchestrator.embedding.client as embedding_client


class _BytesResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


def test_embed_texts_forces_ollama_for_hf_model_name(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_urlopen(req, timeout=60):  # noqa: ANN001, ANN201
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _BytesResponse(b'{"embeddings": [[0.11, 0.22, 0.33]]}')

    monkeypatch.setattr(embedding_client.urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(
        embedding_client,
        "_get_hf_model",
        lambda _model_name: (_ for _ in ()).throw(RuntimeError("hf path should not be used")),
    )

    out = embedding_client.embed_texts(
        ["테스트 문장"],
        model="dragonkue/multilingual-e5-small-ko-v2",
        backend="ollama",
        ollama_url="http://test-ollama:11434",
    )

    assert out == [[0.11, 0.22, 0.33]]
    assert captured["url"] == "http://test-ollama:11434/api/embed"
    assert captured["payload"] == {
        "model": "dragonkue/multilingual-e5-small-ko-v2",
        "input": ["테스트 문장"],
    }


def test_embed_texts_auto_uses_hf_for_model_with_slash(monkeypatch):
    class _FakeHFModel:
        def encode(self, texts, convert_to_numpy=True):  # noqa: ANN001, ARG002
            class _Vec:
                def __init__(self, values):
                    self._values = values

                def tolist(self):
                    return list(self._values)

            return [_Vec([0.1, 0.2]), _Vec([0.3, 0.4])][: len(texts)]

    monkeypatch.setattr(embedding_client, "_get_hf_model", lambda _model_name: _FakeHFModel())

    out = embedding_client.embed_texts(
        ["a", "b"],
        model="dragonkue/multilingual-e5-small-ko-v2",
        backend="auto",
    )

    assert out == [[0.1, 0.2], [0.3, 0.4]]
