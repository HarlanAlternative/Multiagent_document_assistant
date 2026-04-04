from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.conversations import ConversationDetailRead, ConversationSummaryRead
from app.services.qa.qa_service import QAService

router = APIRouter()
qa_service = QAService()


@router.get("", response_model=list[ConversationSummaryRead])
def list_conversations(project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[ConversationSummaryRead]:
    return qa_service.list_conversations(db=db, project_id=project_id)


@router.get("/{conversation_id}", response_model=ConversationDetailRead)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ConversationDetailRead:
    return qa_service.get_conversation(db=db, conversation_id=conversation_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    qa_service.delete_conversation(db=db, conversation_id=conversation_id, project_id=project_id)
