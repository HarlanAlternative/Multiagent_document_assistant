# Multi-Agent Personal Knowledge Copilot

A production-style personal knowledge assistant that ingests private documents, indexes them for retrieval, and answers grounded questions with citations. The current implementation focuses on the backend MVP so the ingestion and private-document QA path is stable before web augmentation and richer orchestration are added.

## What Is Implemented

- FastAPI backend with modular route/service boundaries
- document lifecycle APIs: upload, list, detail, delete, reindex
- PDF parsing via PyMuPDF
- PPTX parsing via python-pptx
- chunking that preserves page and slide metadata
- Qdrant-backed vector retrieval with metadata payload filtering
- local vector fallback when Qdrant is unavailable
- Tavily-backed web search agent with graceful fallback
- optional OpenAI-compatible and Bedrock-native LLM routing and answer synthesis
- OpenAI and Bedrock embedding support for full-RAG retrieval
- conversation and citation persistence
- route-aware QA response payloads
- Docker Compose for PostgreSQL, Qdrant, backend, and frontend dev runtime

## Current Tradeoffs

- The default vector backend is `qdrant`, with `local` fallback retained for resilience and local-only development.
- Web search requires `SEARCH_ENABLED=true` and a configured `SEARCH_API_KEY`.
- Embeddings are deterministic by default, but the runtime settings can switch to OpenAI or Bedrock embeddings for a true external-embedding RAG path.

## Repository Layout

```text
backend/
  app/
    api/
    core/
    db/
    models/
    schemas/
    services/
  requirements.txt

docs/
  architecture.md
  api-spec.md
  roadmap.md

frontend/
  src/
  package.json
  README.md

infra/
  docker/
  docker-compose.yml
```

## Quick Start

### 1. Backend local setup

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

On Windows PowerShell, use:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

### 2. Docker Compose

```bash
cd infra
docker compose up --build
```

This now starts the full local stack:

- PostgreSQL on `localhost:5433`
- Qdrant on `localhost:6333`
- FastAPI backend on `http://127.0.0.1:8000`
- React frontend on `http://127.0.0.1:5173`

The local Docker PostgreSQL port is mapped to `5433` to avoid clashing with an existing host PostgreSQL service on `5432`.

### 3. Frontend local setup

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The frontend defaults to `http://127.0.0.1:8000/api`. Override with `VITE_API_BASE_URL` if needed.

For the simplest one-command startup, prefer Docker Compose over running the frontend and backend separately.

## API Summary

- `POST /api/documents/upload`
- `GET /api/documents`
- `GET /api/documents/{document_id}`
- `DELETE /api/documents/{document_id}`
- `POST /api/documents/{document_id}/reindex`
- `POST /api/chat/ask`
- `GET /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `GET /api/health`

## Environment Variables

- `DATABASE_URL`
- `QDRANT_URL`
- `QDRANT_COLLECTION_NAME`
- `QDRANT_API_KEY`
- `QDRANT_TIMEOUT_SECONDS`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_EMBEDDING_MODEL`
- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `EMBEDDING_MODEL`
- `BEDROCK_EMBEDDING_MODEL`
- `CHAT_MODEL`
- `ROUTER_MODEL`
- `ANSWER_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `SEARCH_API_KEY`
- `SEARCH_PROVIDER`
- `SEARCH_TOP_K`
- `SEARCH_TIMEOUT_SECONDS`
- `FILE_STORAGE_PATH`
- `VECTOR_STORE`
- `ROUTER_PROVIDER`
- `EMBEDDING_PROVIDER`
- `ANSWER_PROVIDER`
- `RETRIEVAL_SCORE_THRESHOLD`

## LLM Configuration

To enable OpenAI-compatible LLM routing and answer synthesis, configure these values in `backend/.env`:

```powershell
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_WIRE_API=chat_completions
CHAT_MODEL=gpt-4o-mini
ROUTER_PROVIDER=llm
ANSWER_PROVIDER=llm
LLM_TIMEOUT_SECONDS=30
```

Optional overrides:

```powershell
ROUTER_MODEL=gpt-4o-mini
ANSWER_MODEL=gpt-4o-mini
```

If the LLM call fails or is not configured, the backend falls back to heuristic routing and extractive answer synthesis.

## OpenAI Full-RAG Configuration

If you already have an OpenAI key configured, this is the fastest way to move the app to a real external-embedding RAG stack:

```powershell
VECTOR_STORE=qdrant
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
ROUTER_PROVIDER=llm
ANSWER_PROVIDER=llm
```

After switching those settings, use the project-level `Reindex all documents` action so existing chunks are re-embedded into Qdrant.

## Bedrock Full-RAG Configuration

To move from the local deterministic demo path to a fuller RAG setup, use:

```powershell
VECTOR_STORE=qdrant
EMBEDDING_PROVIDER=bedrock
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=
```

Then configure runtime chat settings to `provider_name=bedrock` and pick a Bedrock chat-capable model such as a Claude or Nova model available in your AWS account. The frontend Settings page now supports Bedrock region/credential fields, Bedrock model loading, embedding provider selection, and vector-store selection.

When using Docker Compose, the backend container now reads `backend/.env` directly, so the same LLM settings are picked up by `docker compose up --build`.

If your gateway prefers the Responses API, set:

```powershell
OPENAI_WIRE_API=responses
```

## Web Search Configuration

To enable hybrid QA and `web_only` mode, configure a Tavily API key in `backend/.env`:

```powershell
SEARCH_ENABLED=true
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=tvly-your-key
SEARCH_TOP_K=5
SEARCH_TIMEOUT_SECONDS=8
```

If web search is unavailable or returns no usable results, the backend logs the failure and degrades gracefully. `private_plus_web` still answers from uploaded documents when possible, while `web_only` refuses when no external evidence is available.

## Demo Flow

1. Upload a PDF or PPTX through `POST /api/documents/upload`.
2. Confirm ingestion with `GET /api/documents`.
3. Ask a grounded question through `POST /api/chat/ask`.
4. Inspect citations and retrieved chunks in the response.
5. Delete the document and verify it no longer appears in retrieval results.

## Recommended Next Step

Run a full end-to-end demo with real uploads and hybrid QA, then replace the extractive answer path with an OpenAI-compatible provider while keeping the current API contracts stable.

## Accuracy-First Recommendation

If your priority is retrieval quality rather than a lightweight local demo path, use:

- `VECTOR_STORE=qdrant`
- `EMBEDDING_PROVIDER=bedrock`
- `BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0`
- `ROUTER_PROVIDER=llm`
- `ANSWER_PROVIDER=llm`

After changing any of those retrieval-related settings, reindex the whole project so existing chunks are re-embedded under the new configuration. The Documents page now includes a project-level `Reindex all documents` action for that purpose.
