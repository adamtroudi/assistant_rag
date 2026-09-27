# syntax=docker/dockerfile:1
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app

RUN groupadd --system assistant \
    && useradd --system --gid assistant --create-home assistant \
    && mkdir -p /opt/huggingface \
    && chown -R assistant:assistant /opt/huggingface /app

COPY pyproject.toml ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && python -c "import tomllib; print(chr(10).join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && python -m pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY README.md ./
COPY app ./app
RUN python -m pip install --no-deps .

COPY alembic.ini ./
COPY migrations ./migrations
COPY data/rag_epi_3_machines ./data/rag_epi_3_machines
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown -R assistant:assistant /app

USER assistant

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
