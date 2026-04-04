import math
from dataclasses import dataclass
from typing import Protocol

from app.models.chunk import Chunk
from sqlalchemy.orm import Session


@dataclass(slots=True)
class VectorSearchHit:
    chunk: Chunk
    score: float


class VectorStore(Protocol):
    def ensure_collection(self) -> None:
        ...

    def upsert_chunks(self, db: Session, chunks: list[Chunk]) -> None:
        ...

    def delete_document(self, db: Session, document_id: str) -> None:
        ...

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
        ...


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot_product / (left_norm * right_norm)
