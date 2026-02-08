from app.core.settings import Settings


def test_cors_origins_fallback_defaults(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    cfg = Settings()
    assert cfg.cors_origins_list == [
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://192.168.0.4:5175",
    ]


def test_cors_origins_parsing(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    cfg = Settings()
    assert cfg.cors_origins_list == ["https://a.example", "https://b.example"]


def test_database_url_resolution_with_parts(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "db-host")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "olala_test")
    monkeypatch.setenv("DB_USER", "tester")
    monkeypatch.setenv("DB_PASSWORD", "secret")

    cfg = Settings()
    assert cfg.database_url_resolved == "postgresql://tester:secret@db-host:5433/olala_test"


def test_database_url_resolution_prefers_explicit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@explicit-host:5432/prod")
    cfg = Settings()
    assert cfg.database_url_resolved == "postgresql://u:p@explicit-host:5432/prod"


def test_bool_parsing_for_wiki_embeddings_ready(monkeypatch):
    monkeypatch.setenv("WIKI_EMBEDDINGS_READY", "true")
    cfg = Settings()
    assert cfg.wiki_embeddings_ready is True
