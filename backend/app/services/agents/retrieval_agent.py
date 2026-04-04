from sqlalchemy.orm import Session

from app.schemas.chat import RetrievedChunkRead
from app.services.retrieval.retrieval_service import RetrievalService


class RetrievalAgent:
    def __init__(self, retrieval_service: RetrievalService | None = None) -> None:
        self.retrieval_service = retrieval_service or RetrievalService()

    def retrieve(
        self,
        db: Session,
        question: str,
        conversation_context: str | None = None,
        project_id: str | None = None,
        selected_document_ids: list[str] | None = None,
        file_type: str | None = None,
    ) -> list[RetrievedChunkRead]:
        return self.retrieval_service.retrieve(
            db=db,
            question=question,
            conversation_context=conversation_context,
            project_id=project_id,
            selected_document_ids=selected_document_ids or [],
            file_type=file_type,
        )
