import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.embeddings.embedding_service import EmbeddingService
from app.services.vectorstore.base import VectorSearchHit
from app.services.vectorstore.simple_vector_store import LocalVectorStore

logger = logging.getLogger(__name__)


def _qdrant_imports() -> dict[str, Any]:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import (
        Distance,
        FieldCondition,
        Filter,
        FilterSelector,
        MatchAny,
        MatchValue,
        PointStruct,
        VectorParams,
    )

    return {
        "QdrantClient": QdrantClient,
        "Distance": Distance,
        "FieldCondition": FieldCondition,
        "Filter": Filter,
        "FilterSelector": FilterSelector,
        "MatchAny": MatchAny,
        "MatchValue": MatchValue,
        "PointStruct": PointStruct,
        "VectorParams": VectorParams,
    }


class QdrantVectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        try:
            self.vector_size = EmbeddingService(dimensions=settings.embedding_dimensions).vector_size()
        except Exception as exc:
            logger.warning("Could not determine the embedding size, assuming %s: %s", settings.embedding_dimensions, exc)
            self.vector_size = settings.embedding_dimensions
        # A Qdrant collection has a fixed vector size, so other sizes (e.g. local models) get their own collection.
        self.collection_name = (
            settings.qdrant_collection_name
            if self.vector_size == settings.embedding_dimensions
            else f"{settings.qdrant_collection_name}_{self.vector_size}d"
        )
        self.qdrant_url = settings.qdrant_url
        self.qdrant_api_key = settings.qdrant_api_key
        self.timeout = settings.qdrant_timeout_seconds
        self.fallback_store = LocalVectorStore()
        self._collection_ensured = False
        self._client: Any | None = None
        self._client_disabled = False

    def ensure_collection(self) -> None:
        client = self._get_client()
        if client is None or self._collection_ensured:
            return

        try:
            imports = _qdrant_imports()
            collection_created = False
            if not client.collection_exists(self.collection_name):
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=imports["VectorParams"](
                        size=self.vector_size,
                        distance=imports["Distance"].COSINE,
                    ),
                )
                collection_created = True

            if collection_created:
                for field_name in ("project_id", "document_id", "file_type"):
                    try:
                        client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name=field_name,
                            field_schema="keyword",
                        )
                    except Exception as exc:
                        logger.warning(
                            "Qdrant payload index creation failed for %s on %s: %s",
                            field_name,
                            self.collection_name,
                            exc,
                        )
            self._collection_ensured = True
        except Exception as exc:
            logger.warning("Qdrant collection initialization failed, falling back to local store: %s", exc)

    def upsert_chunks(self, db: Session, chunks: list[Chunk]) -> None:
        self.fallback_store.upsert_chunks(db=db, chunks=chunks)
        client = self._get_client()
        if client is None:
            return

        self.ensure_collection()
        try:
            imports = _qdrant_imports()
            chunk_ids = [chunk.id for chunk in chunks]
            stored_chunks = self._load_chunks(db=db, chunk_ids=chunk_ids)
            points = [
                imports["PointStruct"](
                    id=chunk.vector_id or chunk.id,
                    vector=list(chunk.embedding or []),
                    payload=self._build_payload(chunk),
                )
                for chunk in stored_chunks
                if chunk.embedding
            ]
            if not points:
                return

            client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
        except Exception as exc:
            logger.warning("Qdrant upsert failed, local fallback remains available: %s", exc)

    def delete_document(self, db: Session, document_id: str) -> None:
        self.fallback_store.delete_document(db=db, document_id=document_id)
        client = self._get_client()
        if client is None:
            return
        self.ensure_collection()
        try:
            imports = _qdrant_imports()
            client.delete(
                collection_name=self.collection_name,
                points_selector=imports["FilterSelector"](
                    filter=imports["Filter"](
                        must=[
                            imports["FieldCondition"](
                                key="document_id",
                                match=imports["MatchValue"](value=document_id),
                            )
                        ]
                    )
                ),
                wait=True,
            )
        except Exception as exc:
            logger.warning("Qdrant delete by document failed for %s: %s", document_id, exc)
            raise RuntimeError(f"Failed to delete document vectors from Qdrant for document_id={document_id}") from exc

    def search(
        self,
        db: Session,
        query_embedding: list[float],
        top_k: int,
        query_text: str | None = None,
        project_id: str | None = None,
        document_ids: list[str] | None = None,
        file_type: str | None = None,
    ) -> list[VectorSearchHit]:
        client = self._get_client()
        if client is None:
            return self.fallback_store.search(
                db=db,
                query_embedding=query_embedding,
                top_k=top_k,
                query_text=query_text,
                project_id=project_id,
                document_ids=document_ids,
                file_type=file_type,
            )

        self.ensure_collection()
        try:
            imports = _qdrant_imports()
            query_filter = self._build_filter(
                imports=imports,
                project_id=project_id,
                document_ids=document_ids or [],
                file_type=file_type,
            )
            raw_hits = self._query_points(
                client=client,
                query_embedding=query_embedding,
                query_filter=query_filter,
                top_k=top_k,
            )
            chunk_ids = [
                hit.payload.get("chunk_id")
                for hit in raw_hits
                if getattr(hit, "payload", None) and hit.payload.get("chunk_id")
            ]
            if not chunk_ids:
                return []

            chunks_by_id = {
                chunk.id: chunk
                for chunk in self._load_chunks(db=db, chunk_ids=chunk_ids)
            }
            hits: list[VectorSearchHit] = []
            for hit in raw_hits:
                payload = getattr(hit, "payload", {}) or {}
                chunk_id = payload.get("chunk_id")
                chunk = chunks_by_id.get(chunk_id)
                if not chunk:
                    logger.warning("Qdrant returned chunk_id=%s but no SQL row was found.", chunk_id)
                    continue
                hits.append(VectorSearchHit(chunk=chunk, score=float(hit.score)))
            return hits
        except Exception as exc:
            logger.warning("Qdrant search failed, falling back to local store: %s", exc)
            return self.fallback_store.search(
                db=db,
                query_embedding=query_embedding,
                top_k=top_k,
                query_text=query_text,
                project_id=project_id,
                document_ids=document_ids,
                file_type=file_type,
            )

    def _build_payload(self, chunk: Chunk) -> dict[str, Any]:
        return {
            "chunk_id": chunk.id,
            "project_id": chunk.document.project_id,
            "document_id": chunk.document_id,
            "filename": chunk.document.filename,
            "file_type": chunk.document.file_type,
            "page_number": chunk.page_number,
            "slide_number": chunk.slide_number,
            "content_preview": chunk.content_preview or chunk.content[:200],
        }

    def _build_filter(
        self,
        imports: dict[str, Any],
        project_id: str | None,
        document_ids: list[str],
        file_type: str | None,
    ) -> Any | None:
        must_conditions: list[Any] = []
        if project_id:
            must_conditions.append(
                imports["FieldCondition"](
                    key="project_id",
                    match=imports["MatchValue"](value=project_id),
                )
            )
        if document_ids:
            match = (
                imports["MatchValue"](value=document_ids[0])
                if len(document_ids) == 1
                else imports["MatchAny"](any=document_ids)
            )
            must_conditions.append(imports["FieldCondition"](key="document_id", match=match))
        if file_type:
            must_conditions.append(
                imports["FieldCondition"](
                    key="file_type",
                    match=imports["MatchValue"](value=file_type),
                )
            )
        if not must_conditions:
            return None
        return imports["Filter"](must=must_conditions)

    def _get_client(self) -> Any | None:
        if self._client_disabled:
            return None
        if self._client is not None:
            return self._client
        if not self.qdrant_url:
            logger.warning("Qdrant is configured but QDRANT_URL is missing. Using local vector store fallback.")
            self._client_disabled = True
            return None

        try:
            imports = _qdrant_imports()
            self._client = imports["QdrantClient"](
                url=self.qdrant_url,
                api_key=self.qdrant_api_key or None,
                timeout=self.timeout,
                check_compatibility=False,
            )
            return self._client
        except ImportError as exc:
            logger.warning("qdrant-client is not installed, using local vector store fallback: %s", exc)
            self._client_disabled = True
            return None
        except Exception as exc:
            logger.warning("Failed to initialize Qdrant client, using local vector store fallback: %s", exc)
            self._client_disabled = True
            return None

    def _load_chunks(self, db: Session, chunk_ids: list[str]) -> list[Chunk]:
        if not chunk_ids:
            return []

        statement = (
            select(Chunk)
            .options(joinedload(Chunk.document))
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.id.in_(chunk_ids))
            .where(Document.status == "indexed")
        )
        chunks = list(db.scalars(statement).all())
        chunks_by_id = {chunk.id: chunk for chunk in chunks}
        return [chunks_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in chunks_by_id]

    def _query_points(
        self,
        *,
        client: Any,
        query_embedding: list[float],
        query_filter: Any | None,
        top_k: int,
    ) -> list[Any]:
        if hasattr(client, "search"):
            return client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )

        response = client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return list(getattr(response, "points", []) or [])
