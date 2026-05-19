from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from app.database import get_db
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.models.workflow import Workflow
from app.models.execution import Execution
from app.schemas.execution import ExecuteRequest, ExecutionResponse, ExecutionListResponse
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.utils.errors import NotFoundException, BadRequestException

router = APIRouter()


@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResponse)
async def execute_workflow(
    workspace_id: str,
    workflow_id: str,
    request: ExecuteRequest,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    # Get workflow
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.workspace_id == workspace_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundException("Workflow")

    if not workflow.flow_definition.get("nodes"):
        raise BadRequestException("Workflow has no nodes to execute")

    # Create execution record
    execution = Execution(
        workflow_id=workflow.id,
        workspace_id=workspace_id,
        workflow_version=workflow.version,
        status="pending",
        trigger_type="manual",
        input_data=request.input_data,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    if request.async_execution:
        # Dispatch to Celery worker
        from app.workers.execution_worker import run_workflow_task
        run_workflow_task.delay(execution.id)
    else:
        # Execute synchronously
        from app.engine.executor import WorkflowExecutor
        executor = WorkflowExecutor(db)
        await executor.execute(execution.id)
        await db.refresh(execution)

    return execution


@router.get("/executions", response_model=ExecutionListResponse)
async def list_executions(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
    workflow_id: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Execution).where(Execution.workspace_id == workspace_id)
    count_query = select(func.count()).select_from(Execution).where(Execution.workspace_id == workspace_id)

    if workflow_id:
        query = query.where(Execution.workflow_id == workflow_id)
        count_query = count_query.where(Execution.workflow_id == workflow_id)

    if status:
        query = query.where(Execution.status == status)
        count_query = count_query.where(Execution.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    offset = (page - 1) * limit
    query = query.order_by(Execution.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    executions = result.scalars().all()

    execution_responses = []
    for e in executions:
        res = ExecutionResponse.model_validate(e)
        res.execution_trace = None
        execution_responses.append(res)

    return ExecutionListResponse(executions=execution_responses, total=total)


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    workspace_id: str,
    execution_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Execution).where(
            Execution.id == execution_id,
            Execution.workspace_id == workspace_id,
        )
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise NotFoundException("Execution")
    return execution


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    workspace_id: str,
    execution_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Execution).where(
            Execution.id == execution_id,
            Execution.workspace_id == workspace_id,
        )
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise NotFoundException("Execution")

    if execution.status in ("completed", "failed", "cancelled"):
        raise BadRequestException(f"Cannot cancel execution with status: {execution.status}")

    execution.status = "cancelled"
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True}
