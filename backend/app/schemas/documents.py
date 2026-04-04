from datetime import datetime

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    id: str
    project_id: str | None = None
    filename: str
    file_type: str
    file_size: int
    status: str
    checksum: str
    page_count: int | None = None
    slide_count: int | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DocumentDetailRead(DocumentRead):
    storage_path: str
    error_message: str | None = None
    chunk_count: int = 0


class DocumentUploadResponse(BaseModel):
    document_id: str
    project_id: str | None = None
    filename: str
    status: str


class DocumentRenameRequest(BaseModel):
    filename: str


class DocumentListResponse(BaseModel):
    items: list[DocumentRead] = Field(default_factory=list)
