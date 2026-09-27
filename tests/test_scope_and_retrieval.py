import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import RagChunk
from app.schemas import ChatRequest
from app.services.repository import SqlAlchemyChunkRepository
from app.services.retrieval import Retriever
from app.services.scope import resolve_scope


class FakeEmbedder:
    dimension = 384

    def embed_query(self, question):
        return [1.0] + [0.0] * 383


class CapturingRepository:
    def __init__(self):
        self.machine_ids = None

    def search(self, query_embedding, machine_ids, limit):
        self.machine_ids = machine_ids
        return []


def test_out_of_scope_equipment_is_detected():
    decision = resolve_scope("Compare EPI_PumpStation1 au compteur EPI_TotalLoad", None)
    assert decision.machine_ids == ["EPI_PumpStation1"]
    assert decision.unsupported_mentions


def test_inline_forecast_machine_is_allowed_without_expanding_rag_scope():
    decision = resolve_scope(
        "Analyse EPI_TotalLoad_synthetic_test",
        None,
        {"EPI_TotalLoad_synthetic_test"},
    )
    assert decision.unsupported_mentions == []
    assert decision.machine_ids == []


def test_api_schema_rejects_out_of_scope_machine_parameter():
    with pytest.raises(ValidationError):
        ChatRequest(question="Consommation ?", machine_ids=["TEC_MillingMachine"])  # type: ignore[list-item]


def test_question_machine_name_applies_strict_retrieval_filter():
    repository = CapturingRepository()
    retriever = Retriever(FakeEmbedder(), repository)
    decision = resolve_scope("Quelle est la tension de PumpStation1 ?", None)
    retriever.search("Quelle est la tension de PumpStation1 ?", decision.machine_ids)
    assert repository.machine_ids == ["EPI_PumpStation1"]


def test_explicit_comparison_allows_two_machines():
    decision = resolve_scope("Compare PumpStation1 et PumpStation2", None)
    assert decision.machine_ids == ["EPI_PumpStation1", "EPI_PumpStation2"]


def test_exact_fallback_excludes_other_machine_documents():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    common = {
        "corpus_name": "rag_epi_3_machines",
        "corpus_version": "test",
        "site": "EPI",
        "document_year": 2024,
        "topic": "test",
        "origin": "test",
        "confidence": "test",
        "doc_path": "test.md",
        "source_refs": [{"source_id": "test"}],
        "text_sha256": "0" * 64,
    }
    with Session(engine) as session:
        for chunk_id, machine_id, axis in (
            ("general", None, 0),
            ("pump1", "EPI_PumpStation1", 0),
            ("pump2", "EPI_PumpStation2", 0),
            ("pick", "EPI_PickAndPlace", 0),
        ):
            vector = [0.0] * 384
            vector[axis] = 1.0
            session.add(
                RagChunk(
                    chunk_id=chunk_id,
                    text=chunk_id,
                    machine_id=machine_id,
                    embedding=vector,
                    **common,
                )
            )
        session.commit()
        results = SqlAlchemyChunkRepository(session).search(
            [1.0] + [0.0] * 383,
            ["EPI_PumpStation1"],
            20,
        )

    assert {item.chunk_id for item in results} == {"general", "pump1"}
