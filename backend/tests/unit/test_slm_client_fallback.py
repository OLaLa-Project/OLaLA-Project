from __future__ import annotations

import requests

import app.stages._shared.slm_client as slm_client


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return dict(self._payload)


def test_call_slm2_falls_back_to_settings_ollama_url_when_primary_unreachable(monkeypatch):
    slm_client._default_clients.clear()
    monkeypatch.setattr(slm_client.settings, "slm_stream_enabled", False)
    monkeypatch.setattr(slm_client.settings, "slm2_base_url", "http://ollama:11434/v1")
    monkeypatch.setattr(slm_client.settings, "slm2_api_key", "ollama")
    monkeypatch.setattr(slm_client.settings, "slm2_model", "exaone3.5:7.8b")
    monkeypatch.setattr(slm_client.settings, "ollama_url", "http://olala-ollama:11434")

    calls: list[str] = []

    def _fake_post(url, headers=None, json=None, timeout=None, stream=False):  # noqa: ANN001, ARG001
        calls.append(str(url))
        if str(url).startswith("http://ollama:11434"):
            raise requests.exceptions.ConnectionError("primary host unavailable")
        if str(url) == "http://olala-ollama:11434/api/generate":
            return _FakeResponse(payload={"response": "fallback-ok"})
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(slm_client.requests, "post", _fake_post)

    out = slm_client.call_slm2("system", "user", max_tokens=64)

    assert out == "fallback-ok"
    assert "http://ollama:11434/v1/chat/completions" in calls
    assert "http://olala-ollama:11434/api/generate" in calls

