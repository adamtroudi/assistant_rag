import argparse

from app.config import get_settings
from app.db import SessionLocal
from app.services.corpus import CorpusIndexer, CorpusLoader
from app.services.embeddings import E5Embedder
from app.services.repository import SqlAlchemyChunkRepository


def ingest() -> None:
    settings = get_settings()
    embedder = E5Embedder(settings.embedding_model, settings.embedding_device)
    with SessionLocal() as session:
        indexed, deleted = CorpusIndexer(
            CorpusLoader(settings.rag_corpus_dir),
            embedder,
            SqlAlchemyChunkRepository(session),
        ).run()
    print(f"Corpus indexé: {indexed} fragments; obsolètes supprimés: {deleted}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Administration du corpus RAG EPI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ingest", help="valide et réindexe le corpus de façon idempotente")
    args = parser.parse_args()
    if args.command == "ingest":
        ingest()


if __name__ == "__main__":
    main()

