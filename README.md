# Multi-Agent Personal Knowledge Copilot

English | [简体中文](README.zh-CN.md)

A personal knowledge assistant that answers questions about your own documents. You upload PDF, PPTX, DOCX, TXT or Markdown files, the app indexes them, and every answer cites its source page or slide. Separate agents handle routing, retrieval, web search, answer writing and citations. You can ask in Chinese about English documents, and embeddings can be computed on your own machine. If an external service is unavailable, the app falls back to a local component.

## Features

- **Multi-agent RAG pipeline.** A router agent decides whether a question needs your documents, the web or both. Retrieval, web search, answer and citation agents do the rest.
- **Grounded answers with citations.** Answers use only the retrieved evidence and cite the page or slide. When the documents do not contain the answer, the assistant says so.
- **Chinese and English questions.** Chinese questions are rewritten into English search queries, and the default embedding model is multilingual.
- **On-device embeddings.** A local [fastembed](https://github.com/qdrant/fastembed) model runs on the CPU (`Qwen3-Embedding-0.6B`, int8), so indexing needs no embeddings API.
- **Interchangeable components.**
  - LLMs: any OpenAI-compatible API (OpenAI, DeepSeek and others), Claude, Gemini or AWS Bedrock.
  - Embeddings: the local model, OpenAI, Bedrock or offline hashing.
  - Vector store: Qdrant or a local store.
  - Web search: Tavily or DuckDuckGo.
- **Projects and conversations.** Documents and chat history are grouped by project. Long conversations are summarized, so follow-up questions keep their context.
- **Built-in evaluation.** A labeled question set and a script that measure retrieval and answer quality through the real API.
- **Full stack.** A FastAPI backend, a React frontend and a Docker Compose setup. A Settings page switches providers while the app is running.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, SQLite or PostgreSQL, Qdrant, PyMuPDF, python-pptx, python-docx, fastembed
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, KaTeX

## Results

These results come from 72 test questions (22 in Chinese) about 5 PDF lecture decks with 226 pages. The answers came from DeepSeek (`deepseek-flash`), and embeddings came from the local Qwen3 model.

| Metric | Result |
|---|---|
| Retrieval hit@5 (the page with the answer is retrieved) | 94.4% |
| Retrieval hit@5, Chinese questions | 90.9% |
| Answers graded correct | 87.5% |
| Answers whose every claim is supported by the retrieved text | 97.1% |
| Out-of-scope questions correctly refused | 10/10 |
| Response time | median 5.1 s, p90 9.7 s |
| Time to index 226 pages on a CPU | 62 s |

A separate LLM (`deepseek-v4-pro`) graded correctness and grounding. See [Evaluation](#evaluation) for the method and the baselines.

## How It Works

**Indexing.** Each file is parsed page by page (PDF), slide by slide (PPTX) or as plain text. The text is split into chunks of up to 220 words, and no chunk crosses a page. Each chunk is embedded and stored with its page number.

**Answering a question:**

1. **Route.** In `auto` mode, an LLM chooses between the documents, the web or both. Without an LLM, rules decide.
2. **Rewrite.** Chinese questions and follow-up questions are rewritten into a standalone English search query.
3. **Retrieve.** The system finds 20 candidate chunks, scoring each one by vector similarity combined with keyword overlap.
4. **Rerank.** The candidates are rescored for the type of question (definition, uses, formula or general), and then the LLM reranks them. Usually one or two chunks remain.
5. **Answer.** The LLM answers only from those chunks and refuses if they do not contain the answer. Without an LLM, the most relevant sentences are returned instead.
6. **Cite.** Each answer lists the file and page or slide of its evidence, or the URLs of web results.

Retrieval is chunk-level vector search with reranking. There is no knowledge graph.

## Evaluation

The question set in `backend/eval/dataset.json` has 91 questions about the 5 PDFs:

- 72 test questions, 22 of them in Chinese. Each is labeled with the pages that contain the answer.
- 10 questions that the documents cannot answer, so the correct response is a refusal.
- 9 questions from early development, which are reported separately.

`backend/eval/run_eval.py` sends every question through `POST /api/chat/ask` in `private_only` mode. It records retrieval, citations, response time and token usage. A separate model, `deepseek-v4-pro`, grades each answer against a reference answer and the retrieved evidence.

Results on the 72 test questions, measured on 2026-10-02:

| Metric | No LLM, hash embeddings | DeepSeek, hash embeddings | DeepSeek, local embeddings (default) |
|---|---|---|---|
| Retrieval hit@5 | 70.8% | 88.9% | **94.4%** |
| MRR@5 | 0.588 | 0.889 | **0.944** |
| Retrieval hit@5, Chinese questions | 13.6% | 72.7% | **90.9%** |
| Answers correct | not graded | 87.5% | 87.5% |
| Answers with every claim supported | not graded | 96.9% | 97.1% |
| Citation precision | 45.5% | 79.8% | 85.2% |
| Unanswerable questions refused | 5/10 | 10/10 | 10/10 |
| Response time, median / p90 | 33 ms / 35 ms | 4.0 s / 8.6 s | 5.1 s / 9.7 s |

The local embedding models compared as follows, without an LLM:

| Embedding model | Download | Hit@5 | MRR@5 | Chinese hit@5 | Time per question | Indexing 226 pages |
|---|---|---|---|---|---|---|
| Hash (no model) | - | 70.8% | 0.588 | 3/22 | 33 ms | 0.2 s |
| `paraphrase-multilingual-MiniLM-L12-v2` | 0.22 GB | 75.0% | 0.650 | 6/22 | 66 ms | 2.9 s |
| `jina-embeddings-v2-base-zh` | 0.64 GB | 75.0% | 0.657 | 6/22 | 115 ms | 13.2 s |
| `Qwen3-Embedding-0.6B-Q` (default) | 1.12 GB | 80.6% | 0.693 | 10/22 | 546 ms | 62.0 s |

Per-question results are in `backend/eval/results/`. To reproduce the results:

```powershell
cd backend
.venv\Scripts\python.exe eval\run_eval.py --config offline
.venv\Scripts\python.exe eval\run_eval.py --config deepseek --embedding-provider local --judge-model deepseek-v4-pro
```

Runs that use an LLM read `DEEPSEEK_API_KEY` from the environment or from `backend/.env`. The PDFs are not in the repository. The script looks for them in `backend/storage/demo-run/live-backend-uploads` and matches them by SHA-256. Use `--docs-dir` to point it at another folder.

## Quick Start

### Docker Compose (full stack)

```bash
cd infra
docker compose up --build
```

This starts:

- PostgreSQL on `localhost:5433`, mapped away from `5432` to avoid clashing with a PostgreSQL already on the host
- Qdrant on `localhost:6333`
- the FastAPI backend on `http://127.0.0.1:8000`
- the React frontend on `http://127.0.0.1:5173`

The backend container reads `backend/.env`.

### Backend only

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

On macOS or Linux, activate the virtual environment with `. .venv/bin/activate` and copy the file with `cp .env.example .env`.

`.env.example` points at the Docker PostgreSQL on port `5433`. To run without any services, remove `DATABASE_URL` and set `VECTOR_STORE=local`. The backend then uses SQLite at `backend/storage/app.db`.

### Frontend only

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The frontend calls `http://127.0.0.1:8000/api` by default. Set `VITE_API_BASE_URL` to change it.

## Configuration

You can change most settings on the **Settings** page. They are saved to `backend/storage/runtime_settings.json` and override `.env`. Changes to the LLM, embeddings and vector store apply from the next request. Changes to web search need a backend restart.

### LLM

Set the API key, provider and models on the Settings page, or with `PUT /api/settings/llm`. The key is read only from there, and it is also used for OpenAI embeddings. `OPENAI_API_KEY` in `backend/.env` is not read.

**DeepSeek:** choose the DeepSeek preset. It does three things:

- It sets the base URL to `https://api.deepseek.com/v1` and the wire API to `chat_completions`.
- It offers the models `deepseek-flash` and `deepseek-v4-pro`.
- It switches embeddings to the local model, because DeepSeek has no embeddings API.

Model names and modes can also come from `.env`:

```powershell
CHAT_MODEL=gpt-5-mini
ROUTER_MODEL=gpt-5-mini
ANSWER_MODEL=gpt-5-mini
ROUTER_PROVIDER=llm
ANSWER_PROVIDER=llm
OPENAI_WIRE_API=responses   # or chat_completions
LLM_TIMEOUT_SECONDS=30
```

Without a working LLM, the backend falls back to rule-based routing, heuristic reranking and extractive answers.

### Embeddings and vector store

| Setup | Settings |
|---|---|
| Local model (recommended, no API key) | `EMBEDDING_PROVIDER=local`, optionally `LOCAL_EMBEDDING_MODEL` and `LOCAL_EMBEDDING_CACHE_DIR` |
| Offline hashing (no model) | `EMBEDDING_PROVIDER=deterministic` |
| OpenAI | `EMBEDDING_PROVIDER=openai`, `OPENAI_EMBEDDING_MODEL=text-embedding-3-large` |
| Bedrock | `EMBEDDING_PROVIDER=bedrock`, `BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |

- **Local model:** the default is `Qwen/Qwen3-Embedding-0.6B-Q`. It is downloaded on first use (about 1.1 GB) and cached in `backend/storage/models/`. You can set any model from fastembed's `TextEmbedding.list_supported_models()` instead.
- **Offline hashing:** it only matches shared words, so Chinese questions match English documents only when an LLM rewrites the query.
- **Changing provider:** after changing the embedding provider, use **Reindex all documents** on the Documents page.
- **Vector store:** set `VECTOR_STORE` to `qdrant` or `local`. If Qdrant is unreachable, search falls back to the local store. Embeddings with a size other than `EMBEDDING_DIMENSIONS` (256) get their own Qdrant collection, for example `document_chunks_1024d`.

### Web search

```powershell
SEARCH_ENABLED=true
SEARCH_PROVIDER=duckduckgo   # no API key needed
# or
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=tvly-your-key
SEARCH_TOP_K=5
SEARCH_TIMEOUT_SECONDS=8
```

If web search is unavailable, `private_plus_web` still answers from your documents, and `web_only` refuses.

### Environment variables

| Group | Variables |
|---|---|
| Storage | `DATABASE_URL`, `FILE_STORAGE_PATH`, `MAX_UPLOAD_SIZE_MB` |
| Qdrant | `VECTOR_STORE`, `QDRANT_URL`, `QDRANT_COLLECTION_NAME`, `QDRANT_API_KEY`, `QDRANT_TIMEOUT_SECONDS` |
| LLM | `CHAT_MODEL`, `ROUTER_MODEL`, `ANSWER_MODEL`, `ROUTER_PROVIDER`, `ANSWER_PROVIDER`, `OPENAI_BASE_URL`, `OPENAI_WIRE_API`, `LLM_TIMEOUT_SECONDS` |
| Embeddings | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `OPENAI_EMBEDDING_MODEL`, `BEDROCK_EMBEDDING_MODEL`, `LOCAL_EMBEDDING_MODEL`, `LOCAL_EMBEDDING_CACHE_DIR` |
| AWS | `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` |
| Retrieval | `CHUNK_SIZE_WORDS`, `CHUNK_OVERLAP_WORDS`, `RETRIEVAL_TOP_K`, `RETRIEVAL_SCORE_THRESHOLD` |
| Web search | `SEARCH_ENABLED`, `SEARCH_PROVIDER`, `SEARCH_API_KEY`, `SEARCH_TOP_K`, `SEARCH_TIMEOUT_SECONDS` |

## API

| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Settings | `GET/PUT /api/settings/llm`, `POST /api/settings/llm/models`, `GET/PUT /api/settings/search` |
| Projects | `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{project_id}`, `POST /api/projects/{project_id}/reindex` |
| Documents | `POST /api/documents/upload`, `GET /api/documents`, `GET/PATCH/DELETE /api/documents/{document_id}`, `POST /api/documents/{document_id}/reindex` |
| Chat | `POST /api/chat/ask` |
| Conversations | `GET /api/conversations`, `GET/DELETE /api/conversations/{conversation_id}` |

## Project Structure

```text
backend/
  app/
    api/routes/      # health, settings, projects, documents, chat, conversations
    services/
      agents/        # router, retrieval, web search, answer, citation, orchestrator
      retrieval/     # query rewrite, intent rerank, LLM rerank
      llm/           # OpenAI-compatible, Claude, Gemini, Bedrock clients
      embeddings/    # local (fastembed), OpenAI, Bedrock, hashing
      vectorstore/   # Qdrant + local store
      parsing/       # PDF, PPTX, DOCX, TXT/MD
      ...
  eval/
    dataset.json     # 91 labeled questions
    run_eval.py      # runs the questions through the API and scores them
    results/         # per-question results and summary.md
  scripts/
    smoke_test_qdrant.py
  requirements.txt

frontend/
  src/               # pages: Chat, Documents, Settings

infra/
  docker/
  docker-compose.yml
```

## Limitations

- There is no OCR, so scanned PDFs without a text layer cannot be indexed.
- An answer that needs several pages can be incomplete, because the reranker usually keeps one or two chunks.
- The local vector store compares the query with every chunk in Python. Use Qdrant for large collections.
- Uploads are indexed synchronously. With the local model on a CPU, that takes about 0.27 s per page.
- With an external LLM, your questions and the retrieved passages are sent to that provider.
- There is no authentication, so run the app only on your own machine.

## Testing

`backend/scripts/smoke_test_qdrant.py` runs an end-to-end check against PostgreSQL and Qdrant, for example from Docker Compose. It does the following:

1. Uploads a sample PDF and a sample PPTX.
2. Checks that the SQL rows and the Qdrant vectors match.
3. Asks two filtered questions and checks their citations.
4. Deletes the PDF and checks that nothing of it remains.

> **Warning:** the script first deletes every existing document in the configured database. Point `DATABASE_URL` at a throwaway database.

```powershell
cd backend
.venv\Scripts\python.exe scripts\smoke_test_qdrant.py
```

The evaluation script is described under [Evaluation](#evaluation).
