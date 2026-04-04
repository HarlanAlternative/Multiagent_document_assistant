from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.documents import (
    DocumentDetailRead,
    DocumentListResponse,
    DocumentRead,
    DocumentRenameRequest,
    DocumentUploadResponse,
)
from app.services.ingestion.ingestion_service import IngestionService
from app.services.projects.project_service import ProjectService

router = APIRouter()
ingestion_service = IngestionService()
project_service = ProjectService()


def _to_document_read(document) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        project_id=document.project_id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        checksum=document.checksum,
        page_count=document.page_count,
        slide_count=document.slide_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    project = project_service.get_project(db=db, project_id=project_id)
    document = ingestion_service.ingest_upload(db=db, upload=file, project=project)
    return DocumentUploadResponse(
        document_id=document.id,
        project_id=document.project_id,
        filename=document.filename,
        status=document.status,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> DocumentListResponse:
    documents = ingestion_service.list_documents(db=db, project_id=project_id)
    return DocumentListResponse(items=[_to_document_read(document) for document in documents])


@router.get("/{document_id}", response_model=DocumentDetailRead)
def get_document(document_id: str, project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> DocumentDetailRead:
    document = ingestion_service.get_document(db=db, document_id=document_id, project_id=project_id)
    return DocumentDetailRead(
        **_to_document_read(document).model_dump(),
        storage_path=document.storage_path,
        error_message=document.error_message,
        chunk_count=ingestion_service.count_chunks(db=db, document_id=document_id),
    )


@router.patch("/{document_id}", response_model=DocumentRead)
def rename_document(
    document_id: str,
    payload: DocumentRenameRequest,
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DocumentRead:
    document = ingestion_service.get_document(db=db, document_id=document_id, project_id=project_id)
    document = ingestion_service.rename_document(db=db, document=document, filename=payload.filename)
    return _to_document_read(document)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> None:
    document = ingestion_service.get_document(db=db, document_id=document_id, project_id=project_id)
    ingestion_service.delete_document(db=db, document=document)


@router.post("/{document_id}/reindex", response_model=DocumentUploadResponse)
def reindex_document(document_id: str, project_id: str | None = Query(default=None), db: Session = Depends(get_db)) -> DocumentUploadResponse:
    document = ingestion_service.get_document(db=db, document_id=document_id, project_id=project_id)
    document = ingestion_service.reindex_document(db=db, document=document)
    return DocumentUploadResponse(
        document_id=document.id,
        project_id=document.project_id,
        filename=document.filename,
        status=document.status,
    )
