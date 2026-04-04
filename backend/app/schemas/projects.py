from datetime import datetime

from pydantic import BaseModel, Field


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str | None = None
    memory: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ProjectListResponse(BaseModel):
    items: list[ProjectRead] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    memory: str | None = Field(default=None, max_length=4000)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    memory: str | None = Field(default=None, max_length=4000)


class ProjectReindexResponse(BaseModel):
    project_id: str
    reindexed_document_ids: list[str] = Field(default_factory=list)
    failed_documents: list[str] = Field(default_factory=list)
