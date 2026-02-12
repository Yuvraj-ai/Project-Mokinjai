from pydantic import BaseModel
from datetime import datetime
from typing import Any


class ExecuteRequest(BaseModel):
    input_data: dict[str, Any] = {}
    async_execution: bool = False


class NodeExecutionLog(BaseModel):
    node_id: str
    node_type: str
    status: str
    inputs: dict[str, Any] | None = None
    outputs: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionResponse(BaseModel):
    id: str
    workflow_id: str | None = None
    workspace_id: str
    workflow_version: int | None = None
    status: str
    trigger_type: str | None = None
    input_data: dict | None = None
    output_data: dict | None = None
    error_message: str | None = None
    execution_trace: dict | None = None
    execution_time_ms: int | None = None
    token_usage: dict | None = None
    cost_usd: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionListResponse(BaseModel):
    executions: list[ExecutionResponse]
    total: int
