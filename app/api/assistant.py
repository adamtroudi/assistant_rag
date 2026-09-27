import secrets
from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.schemas import ChatRequest, ChatResponse
from app.services.assistant import AssistantService
from app.services.embeddings import E5Embedder
from app.services.forecasts import ForecastFileAdapter, ForecastValidationError
from app.services.llm import LLMNotConfiguredError, LLMResponseError, OpenAICompatibleLLMClient
from app.services.repository import SqlAlchemyChunkRepository
from app.services.retrieval import Retriever

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@lru_cache
def _embedder(model_name: str, device: str) -> E5Embedder:
    return E5Embedder(model_name, device)


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.assistant_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ASSISTANT_API_KEY n'est pas configurée",
        )
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.assistant_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="clé API invalide")


def get_assistant_service(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AssistantService:
    repository = SqlAlchemyChunkRepository(session)
    retriever = Retriever(
        _embedder(settings.embedding_model, settings.embedding_device),
        repository,
        settings.rag_top_k,
    )
    llm = OpenAICompatibleLLMClient(
        settings.llm_base_url,
        settings.llm_model,
        settings.llm_api_key,
        settings.llm_timeout_seconds,
    )
    return AssistantService(
        retriever,
        llm,
        ForecastFileAdapter(settings.forecast_results_path),
        settings.rag_corpus_dir,
        settings.forecast_default_unit,
        settings.forecast_naive_timezone,
    )


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
def chat(
    request: ChatRequest,
    service: AssistantService = Depends(get_assistant_service),
) -> ChatResponse:
    try:
        return service.chat(request)
    except ForecastValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
