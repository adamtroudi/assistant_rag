from typing import Protocol

from app.services.embeddings import Embedder, normalized_vector
from app.services.repository import RetrievedChunk


class SearchRepository(Protocol):
    def search(
        self, query_embedding: list[float], machine_ids: list[str], limit: int
    ) -> list[RetrievedChunk]: ...


class Retriever:
    def __init__(self, embedder: Embedder, repository: SearchRepository, top_k: int = 6) -> None:
        self.embedder = embedder
        self.repository = repository
        self.top_k = top_k

    def search(self, question: str, machine_ids: list[str]) -> list[RetrievedChunk]:
        query_embedding = normalized_vector(self.embedder.embed_query(question))
        return self.repository.search(query_embedding, machine_ids, self.top_k)

