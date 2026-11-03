"""Playground session schemas (plan Task 2)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    agent_id: str


class ChatSessionUpdate(BaseModel):
    title: str | None = None


class ChatSessionResponse(BaseModel):
    id: str
    workspace_id: str
    agent_id: str
    title: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]
    total: int


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    reasoning: str | None
    activity: list[dict[str, Any]] | None
    structured: dict[str, Any] | None
    status: str | None
    usage: dict[str, Any] | None
    cost_usd: float | None
    execution_id: str | None
    created_at: datetime


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: list[ChatMessageResponse]


class PlaygroundChatRequest(BaseModel):
    content: str = Field(min_length=1)
