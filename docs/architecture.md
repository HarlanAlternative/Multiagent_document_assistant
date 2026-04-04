# Architecture Overview

## Current Phase

The repository currently implements the backend MVP foundation:

- FastAPI application with modular route/service boundaries
- SQLAlchemy models for documents, chunks, conversations, messages, and citations
- document ingestion pipeline for PDF and PPTX
- deterministic embedding pipeline with Qdrant-backed similarity search
- private-document question answering with route metadata and citations

## Core Backend Modules

### API Layer

- `app/api/routes/documents.py`: upload, list, detail, delete, reindex
- `app/api/routes/chat.py`: question answering entrypoint
- `app/api/routes/conversations.py`: conversation history APIs
- `app/api/routes/health.py`: service health

### Ingestion Pipeline

1. `FileStorageService` saves the original file and computes checksum.
2. `ParserFactory` dispatches to `PDFParser` or `PPTXParser`.
3. `ChunkService` preserves page/slide lineage while splitting long source units.
4. `EmbeddingService` converts chunks into vectors.
5. `QdrantVectorStore` stores vectors persistently and supports metadata filters and document-level deletion.
6. `IngestionService` persists document metadata and chunk artifacts.

### QA Flow

1. `RouterAgent` resolves the route.
2. `RetrievalAgent` retrieves top-k chunks.
3. `AnswerAgent` synthesizes a grounded answer from private evidence.
4. `CitationAgent` formats source references.
5. `QAService` stores messages and citations under a conversation.

## Extension Points

- `services/vectorstore/factory.py` isolates the vector backend choice via `VECTOR_STORE=qdrant|local`.
- `services/search/web_search_service.py` and `agents/search_agent.py` reserve the phase-2 web-search path.
- `RouterAgent` already exposes route control for future `private_plus_web` and `web_only` flows.

## Notes

- The default retrieval backend is Qdrant with cosine similarity and payload filtering on `document_id` and `file_type`.
- If Qdrant is unavailable, the app logs the failure and falls back to the local SQL-backed vector path.
- The current answer generator is extractive to keep the private QA path fully local and deterministic.
