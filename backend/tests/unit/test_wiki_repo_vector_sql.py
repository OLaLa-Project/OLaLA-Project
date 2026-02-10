from __future__ import annotations

from app.gateway.database.repos.wiki_repo import WikiRepository as GatewayWikiRepository
from app.orchestrator.database.repos.wiki_repo import WikiRepository as OrchestratorWikiRepository


class _Rows:
    def all(self):
        return []


class _FakeDB:
    def __init__(self):
        self.last_sql = ""

    def execute(self, statement, params):  # noqa: ARG002
        self.last_sql = str(statement)
        return _Rows()


def test_orchestrator_vector_search_candidates_filters_null_embeddings():
    db = _FakeDB()
    repo = OrchestratorWikiRepository(db)  # type: ignore[arg-type]
    repo.vector_search_candidates("[0.1,0.2]", limit=5)

    assert "WHERE c.embedding IS NOT NULL" in db.last_sql
    assert "ORDER BY c.embedding <=> (:qvec)::vector" in db.last_sql
    assert "LIMIT :ann_limit" in db.last_sql
    assert "NULLS LAST" in db.last_sql


def test_gateway_vector_search_candidates_filters_null_embeddings():
    db = _FakeDB()
    repo = GatewayWikiRepository(db)  # type: ignore[arg-type]
    repo.vector_search_candidates("[0.1,0.2]", limit=5)

    assert "WHERE c.embedding IS NOT NULL" in db.last_sql
    assert "ORDER BY c.embedding <=> (:qvec)::vector" in db.last_sql
    assert "LIMIT :ann_limit" in db.last_sql
    assert "NULLS LAST" in db.last_sql
