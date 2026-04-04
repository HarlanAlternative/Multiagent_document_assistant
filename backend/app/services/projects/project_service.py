from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.project import Project
from app.services.ingestion.ingestion_service import IngestionService


class ProjectService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ingestion_service = IngestionService()

    def ensure_default_project(self, db: Session) -> Project:
        statement = select(Project).order_by(Project.created_at.asc())
        existing = db.scalar(statement)
        if existing:
            return existing

        project = Project(
            name=self.settings.default_project_name,
            description="Default workspace for documents and grounded QA.",
            memory="",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def backfill_unscoped_records(self, db: Session, default_project: Project) -> None:
        db.execute(
            update(Document)
            .where(Document.project_id.is_(None))
            .values(project_id=default_project.id)
        )
        db.execute(
            update(Conversation)
            .where(Conversation.project_id.is_(None))
            .values(project_id=default_project.id)
        )
        db.commit()

    def list_projects(self, db: Session) -> list[Project]:
        statement = select(Project).order_by(Project.updated_at.desc(), Project.created_at.desc())
        return list(db.scalars(statement).all())

    def get_project(self, db: Session, project_id: str) -> Project:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        return project

    def create_project(self, db: Session, *, name: str, description: str | None = None, memory: str | None = None) -> Project:
        normalized_name = name.strip()
        if not normalized_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project name is required.")

        existing = db.scalar(select(Project).where(Project.name == normalized_name))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A project with this name already exists.")

        project = Project(
            name=normalized_name,
            description=(description.strip() if description else None),
            memory=(memory.strip() if memory else ""),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def update_project(
        self,
        db: Session,
        *,
        project: Project,
        name: str | None = None,
        description: str | None = None,
        memory: str | None = None,
    ) -> Project:
        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project name cannot be empty.")
            existing = db.scalar(select(Project).where(Project.name == normalized_name, Project.id != project.id))
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A project with this name already exists.")
            project.name = normalized_name
        if description is not None:
            project.description = description.strip() or None
        if memory is not None:
            project.memory = memory.strip()

        project.updated_at = datetime.now(timezone.utc)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def delete_project(self, db: Session, *, project: Project) -> Project | None:
        documents = list(
            db.scalars(
                select(Document).where(Document.project_id == project.id)
            ).all()
        )
        for document in documents:
            self.ingestion_service.delete_document(db=db, document=document)

        conversations = list(
            db.scalars(
                select(Conversation).where(Conversation.project_id == project.id)
            ).all()
        )
        for conversation in conversations:
            db.delete(conversation)

        db.flush()
        db.delete(project)
        db.commit()

        remaining_project = db.scalar(select(Project).order_by(Project.updated_at.desc(), Project.created_at.desc()))
        if remaining_project:
            return remaining_project
        return self.ensure_default_project(db)

    def reindex_project(self, db: Session, *, project: Project) -> tuple[list[str], list[str]]:
        documents = list(
            db.scalars(
                select(Document)
                .where(Document.project_id == project.id)
                .order_by(Document.created_at.asc())
            ).all()
        )
        reindexed_document_ids: list[str] = []
        failed_documents: list[str] = []
        for document in documents:
            try:
                self.ingestion_service.reindex_document(db=db, document=document)
                reindexed_document_ids.append(document.id)
            except Exception:
                failed_documents.append(document.filename)
        return reindexed_document_ids, failed_documents

    def append_memory_entry(self, db: Session, *, project: Project, question: str, answer: str) -> Project:
        existing = (project.memory or "").strip()
        clean_question = " ".join(question.strip().split())
        clean_answer = " ".join(answer.strip().split())
        if len(clean_question) > 240:
            clean_question = f"{clean_question[:237].rstrip()}..."
        if len(clean_answer) > 900:
            clean_answer = f"{clean_answer[:897].rstrip()}..."

        entry = f"User: {clean_question}\nAssistant: {clean_answer}"
        combined = f"{existing}\n\n{entry}".strip() if existing else entry
        limit = self.settings.project_memory_max_chars
        if len(combined) > limit:
            combined = combined[-limit:].lstrip()
        project.memory = combined
        project.updated_at = datetime.now(timezone.utc)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
