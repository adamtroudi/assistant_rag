from pathlib import Path
from datetime import datetime, timedelta

from app.schemas import ChatRequest
from app.services.assistant import AssistantService
from app.services.forecasts import ForecastFileAdapter
from app.services.llm import LLMClient
from app.services.repository import RetrievedChunk


class FakeRetriever:
    def search(self, question, machine_ids):
        assert machine_ids == ["EPI_PumpStation1"]
        return [
            RetrievedChunk(
                chunk_id="machines_EPI_PumpStation1__alimentation",
                text="SPARK publie 400 V.",
                machine_id="EPI_PumpStation1",
                topic="alimentation",
                origin="verifie_dans_spark",
                confidence="elevee",
                doc_path="knowledge_base/machines/EPI_PumpStation1.md",
                source_refs=[
                    {
                        "source_id": "spark_article",
                        "url": "https://publikationen.bibliothek.kit.edu/1000191069/176128394",
                        "archive_path": None,
                        "locator": "PDF p. 7, tableau 3",
                    }
                ],
                score=0.9,
            )
        ]


class FakeLLM(LLMClient):
    def __init__(self):
        self.payload = None
        self.system_prompt = None

    def generate(self, system_prompt, evidence_payload):
        self.system_prompt = system_prompt
        self.payload = evidence_payload
        return "Fait SPARK : alimentation 400 V [machines_EPI_PumpStation1__alimentation; spark_article]."


def test_citations_are_preserved_and_chat_works_without_forecast(tmp_path):
    llm = FakeLLM()
    service = AssistantService(
        FakeRetriever(),
        llm,
        ForecastFileAdapter(tmp_path / "missing.json"),
        Path("data/rag_epi_3_machines"),
    )
    response = service.chat(
        ChatRequest(question="Quelle tension pour PumpStation1 ?", machine_ids=["EPI_PumpStation1"])
    )

    assert response.forecast_refs == []
    assert response.warnings == []
    assert response.citations[0].chunk_id == "machines_EPI_PumpStation1__alimentation"
    assert response.citations[0].source.source_id == "spark_article"
    assert llm.payload["forecast_kpis"] == []
    assert "machines_EPI_PumpStation1__alimentation" in llm.system_prompt


def test_out_of_scope_answer_does_not_call_llm(tmp_path):
    class FailingLLM(LLMClient):
        def generate(self, system_prompt, evidence_payload):
            raise AssertionError("le LLM ne doit pas être appelé")

    service = AssistantService(
        FakeRetriever(),
        FailingLLM(),
        ForecastFileAdapter(tmp_path / "missing.json"),
        Path("data/rag_epi_3_machines"),
    )
    response = service.chat(ChatRequest(question="Que mesure EPI_TotalLoad ?"))
    assert "hors périmètre" in response.answer
    assert response.citations == []


def test_inline_platform_forecast_is_summarized_in_user_prompt(tmp_path):
    class ForecastOnlyRetriever:
        def search(self, question, machine_ids):
            assert machine_ids == []
            return []

    start = datetime(2025, 1, 1)
    points = [
        {
            "timestamp": (start + timedelta(minutes=5 * index)).isoformat(),
            "predicted_P_total": 1000 + index,
        }
        for index in range(7 * 24 * 12)
    ]
    llm = FakeLLM()
    service = AssistantService(
        ForecastOnlyRetriever(),
        llm,
        ForecastFileAdapter(tmp_path / "missing.json"),
        Path("data/rag_epi_3_machines"),
    )
    response = service.chat(
        ChatRequest(
            question="Quels sont les KPI de EPI_TotalLoad_synthetic_test ?",
            forecast_results={
                "machine": "EPI_TotalLoad_synthetic_test",
                "value_col": "P_total",
                "frequency_minutes": 5,
                "horizon_days": 7,
                "n_points": len(points),
                "forecast": points,
            },
        )
    )

    assert response.forecast_refs[0].machine_id == "EPI_TotalLoad_synthetic_test"
    assert llm.payload["forecast_kpis"][0]["point_count"] == 2016
    assert "forecast" not in llm.payload
    assert "You receive the forecasts and their available validation metrics" in llm.system_prompt
    assert "Do not present forecasts as guaranteed future consumption" in llm.system_prompt
    assert any("uniquement sur la prévision" in warning for warning in response.warnings)
