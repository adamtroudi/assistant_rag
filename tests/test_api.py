from fastapi.testclient import TestClient

from app.api.assistant import get_assistant_service, require_api_key
from app.main import app
from app.schemas import ChatResponse


class StubAssistant:
    def chat(self, request):
        return ChatResponse(answer=f"Reçu: {request.question}")


def test_chat_endpoint_contract_and_route():
    app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_assistant_service] = lambda: StubAssistant()
    try:
        response = TestClient(app).post(
            "/api/assistant/chat",
            json={"question": "Explique PumpStation1", "machine_ids": ["EPI_PumpStation1"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Reçu: Explique PumpStation1",
        "citations": [],
        "forecast_refs": [],
        "warnings": [],
    }


def test_chat_endpoint_rejects_unknown_machine_before_service():
    app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_assistant_service] = lambda: StubAssistant()
    try:
        response = TestClient(app).post(
            "/api/assistant/chat",
            json={"question": "Explique TEC", "machine_ids": ["TEC_Machine"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422

