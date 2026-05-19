from pydantic import BaseModel
from datetime import datetime
from typing import Any


class PositionSchema(BaseModel):
    x: float
    y: float


class NodeSchema(BaseModel):
    id: str
    type: str
    data: dict[str, Any] = {}
    position: PositionSchema


class EdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None


class FlowDefinition(BaseModel):
    nodes: list[NodeSchema] = []
    edges: list[EdgeSchema] = []


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    flow_definition: FlowDefinition = FlowDefinition()


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    flow_definition: FlowDefinition | None = None


class WorkflowResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    flow_definition: dict
    status: str
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse]
    total: int
