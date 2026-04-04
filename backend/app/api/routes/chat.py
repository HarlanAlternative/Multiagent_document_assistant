from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.chat import ChatAskRequest, ChatAskResponse
from app.services.qa.qa_service import QAService

router = APIRouter()
qa_service = QAService()


@router.post("/ask", response_model=ChatAskResponse)
def ask_question(payload: ChatAskRequest, db: Session = Depends(get_db)) -> ChatAskResponse:
    return qa_service.ask(db=db, payload=payload)
