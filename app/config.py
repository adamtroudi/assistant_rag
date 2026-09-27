from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://rag:change-me@localhost:5432/rag_assistant"
    assistant_api_key: str = ""
    rag_corpus_dir: Path = Path("data/rag_epi_3_machines")
    rag_top_k: int = Field(default=6, ge=1, le=20)
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_device: str = "cpu"
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_seconds: float = Field(default=60, gt=0)
    forecast_results_path: Path = Path("forecast_results.json")
    forecast_default_unit: Literal["W", "kW", "kWh"] = "W"
    forecast_naive_timezone: str = "UTC"


@lru_cache
def get_settings() -> Settings:
    return Settings()
