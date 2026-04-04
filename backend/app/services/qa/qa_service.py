from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.citation import Citation
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.project import Project
from app.schemas.chat import ChatAskRequest, ChatAskResponse, CitationRead
from app.schemas.conversations import ConversationDetailRead, ConversationSummaryRead, MessageRead
from app.services.agents.orchestrator import AgentOrchestrator
from app.services.projects.project_service import ProjectService
from app.services.qa.conversation_context_service import ConversationContextService


class QAService:
    def __init__(self, orchestrator: AgentOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or AgentOrchestrator()
        self.project_service = ProjectService()
        self.conversation_context_service = ConversationContextService()

    def ask(self, db: Session, payload: ChatAskRequest) -> ChatAskResponse:
        project = self._resolve_project(db=db, payload=payload)
        conversation = self._get_or_create_conversation(db=db, payload=payload, project=project)
        conversation_context = self.conversation_context_service.prepare_context(db=db, conversation=conversation)

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=payload.question,
        )
        db.add(user_message)
        db.flush()

        result = self.orchestrator.run(
            db=db,
            question=payload.question,
            mode=payload.mode,
            project_id=project.id,
            project_memory=project.memory,
            conversation_context=conversation_context.prompt_context,
            retrieval_context=conversation_context.retrieval_hint,
            selected_document_ids=payload.selected_document_ids,
            file_type=payload.file_type,
        )

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=result.answer,
            route_used=result.route_used,
        )
        db.add(assistant_message)
        db.flush()

        for citation in result.citations:
            db.add(
                Citation(
                    message_id=assistant_message.id,
                    source_kind=citation.source_kind,
                    document_id=citation.document_id,
                    chunk_id=citation.chunk_id,
                    title=citation.title,
                    page_number=citation.page_number,
                    slide_number=citation.slide_number,
                    url=citation.url,
                )
            )

        conversation.updated_at = datetime.now(timezone.utc)
        db.add(conversation)
        self.conversation_context_service.refresh_summary(db=db, conversation=conversation)
        db.commit()
        project = self.project_service.append_memory_entry(
            db=db,
            project=project,
            question=payload.question,
            answer=result.answer,
        )
        db.refresh(assistant_message)
        db.refresh(project)

        return ChatAskResponse(
            answer=result.answer,
            citations=result.citations,
            route_used=result.route_used,
            project_id=project.id,
            conversation_id=conversation.id,
            retrieved_chunks=result.retrieved_chunks,
            web_results=result.web_results,
            confidence_note=result.confidence_note,
            internal_sources=result.internal_sources,
            external_sources=result.external_sources,
            project_memory=project.memory,
            created_at=assistant_message.created_at,
        )

    def list_conversations(self, db: Session, project_id: str | None = None) -> list[ConversationSummaryRead]:
        statement = select(Conversation)
        if project_id:
            statement = statement.where(Conversation.project_id == project_id)
        statement = statement.order_by(Conversation.updated_at.desc())
        conversations = list(db.scalars(statement).all())
        return [
            ConversationSummaryRead(
                id=conversation.id,
                project_id=conversation.project_id,
                title=conversation.title,
                summary=conversation.summary,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            for conversation in conversations
        ]

    def get_conversation(self, db: Session, conversation_id: str) -> ConversationDetailRead:
        statement = (
            select(Conversation)
            .options(selectinload(Conversation.messages).selectinload(Message.citations))
            .where(Conversation.id == conversation_id)
        )
        conversation = db.scalar(statement)
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        ordered_messages = sorted(conversation.messages, key=lambda item: item.created_at)
        return ConversationDetailRead(
            id=conversation.id,
            project_id=conversation.project_id,
            title=conversation.title,
            summary=conversation.summary,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[
                MessageRead(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    route_used=message.route_used,
                    created_at=message.created_at,
                    citations=[
                        CitationRead(
                            source_kind=citation.source_kind,
                            document_id=citation.document_id,
                            chunk_id=citation.chunk_id,
                            title=citation.title,
                            page_number=citation.page_number,
                            slide_number=citation.slide_number,
                            url=citation.url,
                        )
                        for citation in message.citations
                    ],
                )
                for message in ordered_messages
            ],
        )

    def delete_conversation(self, db: Session, conversation_id: str, project_id: str | None = None) -> None:
        conversation = db.get(Conversation, conversation_id)
        if not conversation or (project_id and conversation.project_id != project_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        db.delete(conversation)
        db.commit()

    def _get_or_create_conversation(self, db: Session, payload: ChatAskRequest, project: Project) -> Conversation:
        if payload.conversation_id:
            conversation = db.get(Conversation, payload.conversation_id)
            if not conversation or conversation.project_id != project.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found.",
                )
            return conversation

        title = payload.question[:80].strip()
        if len(payload.question) > 80:
            title = f"{title.rstrip()}..."
        conversation = Conversation(title=title or "New conversation", project_id=project.id)
        db.add(conversation)
        db.flush()
        return conversation

    def _resolve_project(self, db: Session, payload: ChatAskRequest) -> Project:
        if payload.project_id:
            return self.project_service.get_project(db=db, project_id=payload.project_id)
        return self.project_service.ensure_default_project(db)
