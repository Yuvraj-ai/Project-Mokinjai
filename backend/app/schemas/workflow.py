from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Any, Literal

NodeType = Literal["input", "agent", "prompt", "output", "conditional", "transform", "http_request", "knowledge"]
WorkflowStatus = Literal["draft", "published", "archived"]

class PositionSchema(BaseModel):
    x: float
    y: float

class NodeSchema(BaseModel):
    id: str
    type: NodeType
    data: dict[str, Any] = Field(default_factory=dict)
    position: PositionSchema

class EdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None

class FlowDefinition(BaseModel):
    nodes: list[NodeSchema] = Field(default_factory=list)
    edges: list[EdgeSchema] = Field(default_factory=list)

class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    flow_definition: FlowDefinition = Field(default_factory=FlowDefinition)

class WorkflowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    flow_definition: FlowDefinition | None = None

class WorkflowResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    flow_definition: dict | None = None
    status: WorkflowStatus
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

    model_config = {"from_attributes": True}

class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse]
    total: int
