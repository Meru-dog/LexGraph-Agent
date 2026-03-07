FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml* ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --without training 2>/dev/null || \
    pip install fastapi uvicorn[standard] pydantic python-multipart langgraph langchain-core langchain-openai openai neo4j faiss-cpu sentence-transformers langdetect python-dotenv aiofiles

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
