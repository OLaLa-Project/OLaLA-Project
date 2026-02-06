from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from typing import Any
from app.core.settings import settings
from app.orchestrator.database.connection import Base

EMBED_DIM = settings.embed_dim

class WikiPage(Base):
    __tablename__ = "wiki_pages"

    page_id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String, index=True, nullable=False)
    url = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    chunks = relationship(
        "WikiChunk",
        back_populates="page",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class WikiChunk(Base):
    __tablename__ = "wiki_chunks"

    chunk_id = Column(BigInteger, primary_key=True, autoincrement=True)
    page_id = Column(BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), index=True, nullable=False)
    
    chunk_idx = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    
    embedding: Any = Column(Vector(EMBED_DIM), nullable=True)

    page = relationship("WikiPage", back_populates="chunks")
