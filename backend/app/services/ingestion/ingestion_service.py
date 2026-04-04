from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.project import Project
from app.services.chunking.chunk_service import ChunkService
from app.services.embeddings.embedding_service import EmbeddingService
from app.services.parsing.factory import ParserFactory
from app.services.storage.file_storage_service import FileStorageService
from app.services.vectorstore.factory import get_vector_store


class IngestionService:
    def __init__(self) -> None:
        settings = get_settings()
        self.chunk_service = ChunkService(
            chunk_size_words=settings.chunk_size_words,
            chunk_overlap_words=settings.chunk_overlap_words,
        )
        self.embedding_service = EmbeddingService(dimensions=settings.embedding_dimensions)
        self.file_storage_service = FileStorageService()
        self.parser_factory = ParserFactory()

    def ingest_upload(self, db: Session, upload: UploadFile, project: Project) -> Document:
        normalized_filename = Path(upload.filename or "").name.strip()
        if not normalized_filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required.")
        self._ensure_filename_available(db=db, project_id=project.id, filename=normalized_filename)

        stored_file = self.file_storage_service.store_upload(upload)
        document = Document(
            project_id=project.id,
            filename=stored_file.original_filename,
            file_type=stored_file.file_type,
            storage_path=str(stored_file.path),
            file_size=stored_file.file_size,
            checksum=stored_file.checksum,
            status="processing",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            self._index_document(db=db, document=document, file_path=stored_file.path)
        except Exception as exc:
            document.status = "failed"
            document.error_message = getattr(exc, "detail", str(exc))
            db.add(document)
            db.commit()
            raise
        return document

    def reindex_document(self, db: Session, document: Document) -> Document:
        file_path = Path(document.storage_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The original uploaded file is missing from storage.",
            )

        get_vector_store().delete_document(db=db, document_id=document.id)
        db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        document.status = "processing"
        document.error_message = None
        document.page_count = None
        document.slide_count = None
        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            self._index_document(db=db, document=document, file_path=file_path)
        except Exception as exc:
            document.status = "failed"
            document.error_message = getattr(exc, "detail", str(exc))
            db.add(document)
            db.commit()
            raise
        return document

    def delete_document(self, db: Session, document: Document) -> None:
        get_vector_store().delete_document(db=db, document_id=document.id)
        self.file_storage_service.delete_file(Path(document.storage_path))
        db.delete(document)
        db.commit()

    def rename_document(self, db: Session, document: Document, filename: str) -> Document:
        normalized_filename = self._normalize_filename(document=document, filename=filename)
        if normalized_filename == document.filename:
            return document
        self._ensure_filename_available(
            db=db,
            project_id=document.project_id,
            filename=normalized_filename,
            exclude_document_id=document.id,
        )

        document.filename = normalized_filename
        db.add(document)
        db.commit()
        db.refresh(document)

        chunks = list(
            db.scalars(
                select(Chunk)
                .options(joinedload(Chunk.document))
                .where(Chunk.document_id == document.id)
            ).all()
        )
        if chunks:
            get_vector_store().upsert_chunks(db=db, chunks=chunks)
        return document

    def get_document(self, db: Session, document_id: str, project_id: str | None = None) -> Document:
        document = db.get(Document, document_id)
        if not document or (project_id and document.project_id != project_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        return document

    def list_documents(self, db: Session, project_id: str | None = None) -> list[Document]:
        statement = select(Document)
        if project_id:
            statement = statement.where(Document.project_id == project_id)
        statement = statement.order_by(Document.created_at.desc())
        return list(db.scalars(statement).all())

    def count_chunks(self, db: Session, document_id: str) -> int:
        statement = select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
        return int(db.scalar(statement) or 0)

    def _normalize_filename(self, document: Document, filename: str) -> str:
        candidate = Path(filename.strip()).name
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Filename cannot be empty.",
            )

        current_suffix = Path(document.filename).suffix
        current_suffix_lower = current_suffix.lower()
        candidate_path = Path(candidate)
        stem = candidate_path.stem.strip() if candidate_path.suffix else candidate.strip()
        candidate_suffix = candidate_path.suffix.lower()

        if not stem:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Filename must include at least one non-extension character.",
            )

        if current_suffix_lower and candidate_suffix and candidate_suffix != current_suffix_lower:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Filename extension must remain {current_suffix_lower}.",
            )

        normalized = f"{stem}{current_suffix or ''}" if current_suffix else candidate
        if len(normalized) > 255:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Filename is too long.",
            )
        return normalized

    def _ensure_filename_available(
        self,
        db: Session,
        project_id: str | None,
        filename: str,
        exclude_document_id: str | None = None,
    ) -> None:
        statement = select(Document.id).where(
            Document.project_id == project_id,
            func.lower(Document.filename) == filename.lower(),
        )
        if exclude_document_id:
            statement = statement.where(Document.id != exclude_document_id)

        existing_document_id = db.scalar(statement.limit(1))
        if existing_document_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'A document named "{filename}" already exists in this project.',
            )

    def _index_document(self, db: Session, document: Document, file_path: Path) -> None:
        parsed_document = self.parser_factory.parse(file_path=file_path, file_type=document.file_type)
        chunk_payloads = self.chunk_service.build_chunks(parsed_document=parsed_document)

        if not chunk_payloads:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No extractable text was found in the uploaded document.",
            )

        embeddings = self.embedding_service.embed_texts([chunk.content for chunk in chunk_payloads])
        chunk_models: list[Chunk] = []
        for payload, embedding in zip(chunk_payloads, embeddings, strict=True):
            chunk_models.append(
                Chunk(
                    document_id=document.id,
                    chunk_index=payload.chunk_index,
                    content=payload.content,
                    token_count=payload.token_count,
                    source_type=payload.source_type,
                    page_number=payload.page_number,
                    slide_number=payload.slide_number,
                    section_title=payload.section_title,
                    vector_id=f"{document.id}:{payload.chunk_index}",
                    content_preview=payload.content_preview,
                    embedding=embedding,
                )
            )

        document.page_count = parsed_document.page_count
        document.slide_count = parsed_document.slide_count
        document.status = "indexed"
        db.add(document)
        db.add_all(chunk_models)
        db.flush()
        for chunk in chunk_models:
            chunk.vector_id = chunk.id
            db.add(chunk)
        db.commit()
        db.refresh(document)

        get_vector_store().upsert_chunks(db=db, chunks=chunk_models)
