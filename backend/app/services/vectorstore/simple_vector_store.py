from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.vectorstore.base import VectorSearchHit, cosine_similarity
from app.utils.text import tokenize_text


class LocalVectorStore:
    def ensure_collection(self) -> None:
        return None

    def upsert_chunks(self, db: Session, chunks: list[Chunk]) -> None:
        db.flush()

    def delete_document(self, db: Session, document_id: str) -> None:
        db.flush()

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
        statement = (
            select(Chunk)
            .options(joinedload(Chunk.document))
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "indexed")
        )
        if project_id:
            statement = statement.where(Document.project_id == project_id)
        if document_ids:
            statement = statement.where(Chunk.document_id.in_(document_ids))
        if file_type:
            statement = statement.where(Document.file_type == file_type)

        chunks = list(db.scalars(statement).all())
        hits: list[VectorSearchHit] = []
        query_terms = self._tokenize(query_text or "")
        for chunk in chunks:
            if not chunk.embedding:
                continue
            cosine_score = cosine_similarity(query_embedding, list(chunk.embedding))
            lexical_score = self._keyword_overlap(query_terms, self._tokenize(chunk.content))
            score = (0.7 * cosine_score) + (0.3 * lexical_score)
            hits.append(VectorSearchHit(chunk=chunk, score=score))

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    def _tokenize(self, text: str) -> set[str]:
        return set(tokenize_text(text))

    def _keyword_overlap(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        overlap = len(left & right)
        return overlap / max(min(len(left), 5), 1)


SimpleVectorStore = LocalVectorStore
