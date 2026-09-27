import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain import CORPUS_NAME, SUPPORTED_MACHINE_IDS
from app.services.embeddings import Embedder, normalized_vector


class CorpusValidationError(ValueError):
    pass


class RawSourceRef(BaseModel):
    model_config = ConfigDict(extra="allow")
    source_id: str
    url: str | None = None
    archive_path: str | None = None
    locator: str | None = None


class RawChunk(BaseModel):
    model_config = ConfigDict(extra="allow")
    chunk_id: str
    doc_path: str
    machine_id: str | None
    site: str
    year: int
    topic: str
    text: str = Field(min_length=1)
    source_refs: list[RawSourceRef] = Field(min_length=1)
    origin: str
    confidence: str
    indexable: bool = True


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    corpus_name: str
    corpus_version: str
    text: str
    machine_id: str | None
    site: str
    document_year: int
    topic: str
    origin: str
    confidence: str
    doc_path: str
    source_refs: list[dict[str, Any]]
    text_sha256: str
    embedding: list[float]


class CorpusStore(Protocol):
    def replace_corpus(self, records: list[ChunkRecord], corpus_name: str) -> tuple[int, int]: ...


class CorpusLoader:
    def __init__(self, corpus_dir: Path) -> None:
        self.corpus_dir = corpus_dir

    def load(self) -> tuple[str, dict[str, dict[str, str]], list[RawChunk]]:
        required = ("rag_config.json", "rag_chunks.jsonl", "sources.csv", "rag_system_prompt.md")
        missing = [name for name in required if not (self.corpus_dir / name).is_file()]
        if missing:
            raise CorpusValidationError(f"fichiers corpus manquants: {', '.join(missing)}")

        config = json.loads((self.corpus_dir / "rag_config.json").read_text(encoding="utf-8"))
        if set(config.get("supported_machine_ids", [])) != set(SUPPORTED_MACHINE_IDS):
            raise CorpusValidationError("supported_machine_ids ne correspond pas au périmètre autorisé")
        if config.get("site") != "EPI":
            raise CorpusValidationError("seul le site EPI est accepté")

        with (self.corpus_dir / "sources.csv").open(encoding="utf-8-sig", newline="") as handle:
            sources = {row["source_id"]: row for row in csv.DictReader(handle)}
        if not sources:
            raise CorpusValidationError("sources.csv est vide")

        chunks: list[RawChunk] = []
        seen: set[str] = set()
        with (self.corpus_dir / "rag_chunks.jsonl").open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    chunk = RawChunk.model_validate_json(line)
                except Exception as exc:
                    raise CorpusValidationError(f"chunk invalide ligne {line_number}: {exc}") from exc
                if not chunk.indexable:
                    continue
                if chunk.chunk_id in seen:
                    raise CorpusValidationError(f"chunk_id dupliqué: {chunk.chunk_id}")
                seen.add(chunk.chunk_id)
                if chunk.site != "EPI" or (
                    chunk.machine_id is not None and chunk.machine_id not in SUPPORTED_MACHINE_IDS
                ):
                    raise CorpusValidationError(f"chunk hors périmètre: {chunk.chunk_id}")
                unknown_sources = {ref.source_id for ref in chunk.source_refs} - sources.keys()
                if unknown_sources:
                    raise CorpusValidationError(
                        f"source_id inconnu dans {chunk.chunk_id}: {sorted(unknown_sources)}"
                    )
                chunks.append(chunk)

        if not chunks:
            raise CorpusValidationError("aucun chunk indexable")
        version = str(config.get("schema_version") or "unknown")
        return version, sources, chunks


class CorpusIndexer:
    def __init__(self, loader: CorpusLoader, embedder: Embedder, store: CorpusStore) -> None:
        self.loader = loader
        self.embedder = embedder
        self.store = store

    def run(self) -> tuple[int, int]:
        version, _, chunks = self.loader.load()
        embeddings = self.embedder.embed_passages([chunk.text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise CorpusValidationError("le nombre d'embeddings ne correspond pas aux chunks")
        records = [
            ChunkRecord(
                chunk_id=chunk.chunk_id,
                corpus_name=CORPUS_NAME,
                corpus_version=version,
                text=chunk.text,
                machine_id=chunk.machine_id,
                site=chunk.site,
                document_year=chunk.year,
                topic=chunk.topic,
                origin=chunk.origin,
                confidence=chunk.confidence,
                doc_path=chunk.doc_path,
                source_refs=[ref.model_dump() for ref in chunk.source_refs],
                text_sha256=hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
                embedding=normalized_vector(embedding),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        return self.store.replace_corpus(records, CORPUS_NAME)
