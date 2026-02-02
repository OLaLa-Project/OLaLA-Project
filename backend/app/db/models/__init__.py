# Shim for legacy imports
# backend/app/db/models/__init__.py
from app.gateway.database.models.analysis_result import AnalysisResult
from app.gateway.database.models.rag import RagDocument, RagChunk
from app.gateway.database.models.wiki_page import WikiPage, WikiChunk

__all__ = ["AnalysisResult", "RagDocument", "RagChunk", "WikiPage", "WikiChunk"]
