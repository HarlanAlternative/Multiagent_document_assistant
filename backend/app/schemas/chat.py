from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChatMode(str, Enum):
    PRIVATE_ONLY = "private_only"
    PRIVATE_PLUS_WEB = "private_plus_web"
    WEB_ONLY = "web_only"
    AUTO = "auto"


class CitationRead(BaseModel):
    source_kind: str
    document_id: str | None = None
    chunk_id: str | None = None
    title: str
    page_number: int | None = None
    slide_number: int | None = None
    url: str | None = None


class RetrievedChunkRead(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    score: float
    content: str
    content_preview: str
    page_number: int | None = None
    slide_number: int | None = None


class WebSearchResultRead(BaseModel):
    title: str
    url: str
    snippet: str
    source: str
    rank: int


class ChatAskRequest(BaseModel):
    project_id: str | None = None
    question: str = Field(min_length=3, max_length=4000)
    mode: ChatMode = ChatMode.AUTO
    selected_document_ids: list[str] = Field(default_factory=list)
    file_type: str | None = None
    conversation_id: str | None = None


class ChatAskResponse(BaseModel):
    answer: str
    citations: list[CitationRead]
    route_used: str
    project_id: str
    conversation_id: str
    retrieved_chunks: list[RetrievedChunkRead]
    web_results: list[WebSearchResultRead] = Field(default_factory=list)
    confidence_note: str | None = None
    internal_sources: list[CitationRead] = Field(default_factory=list)
    external_sources: list[CitationRead] = Field(default_factory=list)
    project_memory: str | None = None
    created_at: datetime
