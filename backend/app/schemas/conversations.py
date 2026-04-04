from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.chat import CitationRead


class MessageRead(BaseModel):
    id: str
    role: str
    content: str
    route_used: str | None = None
    created_at: datetime
    citations: list[CitationRead] = Field(default_factory=list)


class ConversationSummaryRead(BaseModel):
    id: str
    project_id: str | None = None
    title: str
    summary: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ConversationDetailRead(ConversationSummaryRead):
    messages: list[MessageRead] = Field(default_factory=list)
