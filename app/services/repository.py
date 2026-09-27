from dataclasses import asdict, dataclass

import numpy as np
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import RagChunk
from app.services.corpus import ChunkRecord


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    machine_id: str | None
    topic: str
    origin: str
    confidence: str
    doc_path: str
    source_refs: list[dict[str, object]]
    score: float


class SqlAlchemyChunkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._vector_column_cache: bool | None = None

    def _has_vector_column(self) -> bool:
        if self._vector_column_cache is None:
            bind = self.session.get_bind()
            if bind.dialect.name != "postgresql":
                self._vector_column_cache = False
            else:
                self._vector_column_cache = bool(
                    self.session.scalar(
                        text(
                            "SELECT EXISTS ("
                            "SELECT 1 FROM information_schema.columns "
                            "WHERE table_name = 'rag_chunks' AND column_name = 'embedding_vector'"
                            ")"
                        )
                    )
                )
        return self._vector_column_cache

    def replace_corpus(self, records: list[ChunkRecord], corpus_name: str) -> tuple[int, int]:
        ids = [record.chunk_id for record in records]
        values = [asdict(record) for record in records]
        statement = insert(RagChunk).values(values)
        mutable_columns = {
            column.name: getattr(statement.excluded, column.name)
            for column in RagChunk.__table__.columns
            if column.name not in {"chunk_id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[RagChunk.chunk_id],
            set_={**mutable_columns, "updated_at": text("now()")},
        )
        try:
            self.session.execute(statement)
            deleted = self.session.execute(
                delete(RagChunk).where(
                    RagChunk.corpus_name == corpus_name,
                    RagChunk.chunk_id.not_in(ids),
                )
            ).rowcount
            if self._has_vector_column():
                for record in records:
                    vector_literal = "[" + ",".join(format(value, ".9g") for value in record.embedding) + "]"
                    self.session.execute(
                        text(
                            "UPDATE rag_chunks SET embedding_vector = CAST(:vector AS vector) "
                            "WHERE chunk_id = :chunk_id"
                        ),
                        {"vector": vector_literal, "chunk_id": record.chunk_id},
                    )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return len(records), int(deleted or 0)

    def search(
        self,
        query_embedding: list[float],
        machine_ids: list[str],
        limit: int,
    ) -> list[RetrievedChunk]:
        if self._has_vector_column():
            return self._search_pgvector(query_embedding, machine_ids, limit)
        return self._search_exact(query_embedding, machine_ids, limit)

    def _search_pgvector(
        self, query_embedding: list[float], machine_ids: list[str], limit: int
    ) -> list[RetrievedChunk]:
        vector_literal = "[" + ",".join(format(value, ".9g") for value in query_embedding) + "]"
        rows = self.session.execute(
            text(
                """
                SELECT chunk_id, text, machine_id, topic, origin, confidence, doc_path, source_refs,
                       1 - (embedding_vector <=> CAST(:query_vector AS vector)) AS score
                FROM rag_chunks
                WHERE corpus_name = 'rag_epi_3_machines'
                  AND site = 'EPI'
                  AND embedding_vector IS NOT NULL
                  AND (machine_id IS NULL OR machine_id = ANY(CAST(:machine_ids AS varchar[])))
                ORDER BY embedding_vector <=> CAST(:query_vector AS vector)
                LIMIT :limit
                """
            ),
            {"query_vector": vector_literal, "machine_ids": machine_ids, "limit": limit},
        ).mappings()
        return [RetrievedChunk(**dict(row)) for row in rows]

    def _search_exact(
        self, query_embedding: list[float], machine_ids: list[str], limit: int
    ) -> list[RetrievedChunk]:
        rows = self.session.scalars(
            select(RagChunk).where(
                RagChunk.corpus_name == "rag_epi_3_machines",
                RagChunk.site == "EPI",
                (RagChunk.machine_id.is_(None) | RagChunk.machine_id.in_(machine_ids)),
            )
        ).all()
        query = np.asarray(query_embedding, dtype=np.float32)
        query_norm = float(np.linalg.norm(query))
        scored: list[RetrievedChunk] = []
        for row in rows:
            vector = np.asarray(row.embedding, dtype=np.float32)
            denominator = query_norm * float(np.linalg.norm(vector))
            score = float(np.dot(query, vector) / denominator) if denominator else -1.0
            scored.append(
                RetrievedChunk(
                    chunk_id=row.chunk_id,
                    text=row.text,
                    machine_id=row.machine_id,
                    topic=row.topic,
                    origin=row.origin,
                    confidence=row.confidence,
                    doc_path=row.doc_path,
                    source_refs=row.source_refs,
                    score=score,
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]
