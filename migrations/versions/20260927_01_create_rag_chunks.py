"""Create isolated RAG corpus storage with optional pgvector column.

Revision ID: 20260927_01
Revises: None
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260927_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Managed PostgreSQL roles sometimes cannot install extensions. The JSONB
    # embedding remains authoritative so exact cosine retrieval still works.
    op.execute(
        """
        DO $block$
        BEGIN
          CREATE EXTENSION IF NOT EXISTS vector;
        EXCEPTION
          WHEN insufficient_privilege OR undefined_file THEN
            RAISE NOTICE 'pgvector unavailable; exact application fallback enabled';
        END
        $block$;
        """
    )
    op.create_table(
        "rag_chunks",
        sa.Column("chunk_id", sa.String(length=255), primary_key=True),
        sa.Column("corpus_name", sa.String(length=100), nullable=False),
        sa.Column("corpus_version", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("machine_id", sa.String(length=100), nullable=True),
        sa.Column("site", sa.String(length=20), nullable=False),
        sa.Column("document_year", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=150), nullable=False),
        sa.Column("origin", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.String(length=50), nullable=False),
        sa.Column("doc_path", sa.Text(), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("site = 'EPI'", name="ck_rag_chunks_epi_site"),
        sa.CheckConstraint(
            "machine_id IS NULL OR machine_id IN ('EPI_PumpStation1','EPI_PumpStation2','EPI_PickAndPlace')",
            name="ck_rag_chunks_machine_scope",
        ),
    )
    op.create_index("ix_rag_chunks_corpus", "rag_chunks", ["corpus_name"])
    op.create_index("ix_rag_chunks_site_machine", "rag_chunks", ["site", "machine_id"])
    op.execute(
        """
        DO $block$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vector') THEN
            ALTER TABLE rag_chunks ADD COLUMN embedding_vector vector(384);
          END IF;
        END
        $block$;
        """
    )


def downgrade() -> None:
    op.drop_table("rag_chunks")

