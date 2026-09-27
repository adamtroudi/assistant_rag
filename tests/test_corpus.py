from pathlib import Path
from dataclasses import replace

from app.services.corpus import ChunkRecord, CorpusIndexer, CorpusLoader


CORPUS_DIR = Path("data/rag_epi_3_machines")


class FakeEmbedder:
    dimension = 384

    def embed_passages(self, texts):
        return [[1.0] + [0.0] * 383 for _ in texts]

    def embed_query(self, question):
        return [1.0] + [0.0] * 383


class MemoryStore:
    def __init__(self):
        self.rows: dict[str, ChunkRecord] = {}

    def replace_corpus(self, records, corpus_name):
        incoming = {record.chunk_id for record in records}
        obsolete = [
            chunk_id
            for chunk_id, record in self.rows.items()
            if record.corpus_name == corpus_name and chunk_id not in incoming
        ]
        for chunk_id in obsolete:
            del self.rows[chunk_id]
        self.rows.update({record.chunk_id: record for record in records})
        return len(records), len(obsolete)


def test_ingestion_is_idempotent_and_preserves_supplied_chunks():
    store = MemoryStore()
    indexer = CorpusIndexer(CorpusLoader(CORPUS_DIR), FakeEmbedder(), store)

    assert indexer.run() == (20, 0)
    first_ids = set(store.rows)
    assert indexer.run() == (20, 0)

    assert len(store.rows) == 20
    assert set(store.rows) == first_ids
    assert all(len(row.embedding) == 384 for row in store.rows.values())


def test_reindex_deletes_only_obsolete_chunks_from_this_corpus():
    store = MemoryStore()
    indexer = CorpusIndexer(CorpusLoader(CORPUS_DIR), FakeEmbedder(), store)
    indexer.run()
    template = next(iter(store.rows.values()))
    store.rows["obsolete"] = replace(template, chunk_id="obsolete")
    store.rows["foreign"] = replace(
        template,
        chunk_id="foreign",
        corpus_name="another_corpus",
    )

    assert indexer.run() == (20, 1)
    assert "obsolete" not in store.rows
    assert store.rows["foreign"].corpus_name == "another_corpus"


def test_every_chunk_source_exists_in_sources_csv():
    _, sources, chunks = CorpusLoader(CORPUS_DIR).load()
    assert len(chunks) == 20
    assert all(ref.source_id in sources for chunk in chunks for ref in chunk.source_refs)
