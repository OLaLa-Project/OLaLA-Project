from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from typing import Any

from app.core.settings import settings
from app.orchestrator.database.connection import Base

EMBED_DIM = settings.embed_dim

class RagDocument(Base):
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String, unique=True, index=True, nullable=False)  # 외부 ID(옵션)
    title = Column(String, index=True, nullable=True)
    source = Column(String, index=True, nullable=True)

    # IMPORTANT: python attribute name must NOT be "metadata"
    meta = Column("metadata", JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    chunks = relationship(
        "RagChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("rag_documents.id", ondelete="CASCADE"), index=True, nullable=False)

    chunk_idx = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)

    embedding: Any = Column(Vector(EMBED_DIM), nullable=True)

    # IMPORTANT: python attribute name must NOT be "metadata"
    meta = Column("metadata", JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("RagDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_rag_chunks_document_chunk_idx", "document_id", "chunk_idx", unique=True),
    )
