from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session

from app.orchestrator.database.connection import get_db, transaction
from app.orchestrator.database.repos.wiki_repo import WikiRepository
from app.orchestrator.database.repos.rag_repo import RagRepository
from app.orchestrator.database.repos.analysis_repo import AnalysisRepository

class DatabaseOrchestrator:
    """
    Unified access to database operations.
    API consumers should use usecases, and usecases can use this orchestrator.
    """
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional session."""
        with transaction() as db:
            yield db

    @property
    def wiki_repo(self):
        # Note: Repos usually need a session. 
        # This property pattern typically requires the orchestrator to hold a session
        # OR returns a factory that takes a session.
        # Here we follow the pattern where the caller manages the session via usecase
        # or we return the class for instantiation.
        # Let's return the class so usecases can instantiate with their session.
        return WikiRepository

    @property
    def rag_repo(self):
        return RagRepository

    @property
    def analysis_repo(self):
        return AnalysisRepository

# Singleton instance if needed (though stateless mostly except config)
db_orchestrator = DatabaseOrchestrator()
