import os

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_postgresql_pgvector_is_available_when_configured():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL absent")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        assert connection.scalar(text("SELECT '[1,0]'::vector <=> '[1,0]'::vector")) == 0

