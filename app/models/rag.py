from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

json_type = JSON().with_variant(JSONB(), "postgresql")


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    chunk_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    corpus_name: Mapped[str] = mapped_column(String(100), index=True)
    corpus_version: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    machine_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    site: Mapped[str] = mapped_column(String(20))
    document_year: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(150))
    origin: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[str] = mapped_column(String(50))
    doc_path: Mapped[str] = mapped_column(Text)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(json_type)
    text_sha256: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

