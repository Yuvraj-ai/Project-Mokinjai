from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from app.database import get_db
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.models.workflow import Workflow, WorkflowVersion
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowListResponse,
)
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.utils.errors import NotFoundException

router = APIRouter()


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    workspace_id: str,
    request: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    workflow = Workflow(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        flow_definition=request.flow_definition.model_dump(),
        created_by=current_user.id,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    search: str | None = None,
):
    query = select(Workflow).where(Workflow.workspace_id == workspace_id)
    count_query = select(func.count()).select_from(Workflow).where(Workflow.workspace_id == workspace_id)

    if status:
        query = query.where(Workflow.status == status)
        count_query = count_query.where(Workflow.status == status)

    if search:
        search_filter = Workflow.name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    offset = (page - 1) * limit
    query = query.order_by(Workflow.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    workflows = result.scalars().all()

    return WorkflowListResponse(workflows=workflows, total=total)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workspace_id: str,
    workflow_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.workspace_id == workspace_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundException("Workflow")
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workspace_id: str,
    workflow_id: str,
    request: WorkflowUpdate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.workspace_id == workspace_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundException("Workflow")

    if request.name is not None:
        workflow.name = request.name
    if request.description is not None:
        workflow.description = request.description
    if request.flow_definition is not None:
        workflow.flow_definition = request.flow_definition.model_dump()
        workflow.version += 1

        # Save version snapshot
        version = WorkflowVersion(
            workflow_id=workflow.id,
            version=workflow.version,
            flow_definition=workflow.flow_definition,
            created_by=current_user.id,
        )
        db.add(version)

    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}")
async def delete_workflow(
    workspace_id: str,
    workflow_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.workspace_id == workspace_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundException("Workflow")

    await db.delete(workflow)
    await db.commit()
    return {"success": True}


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_workflow(
    workspace_id: str,
    workflow_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.workspace_id == workspace_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise NotFoundException("Workflow")

    workflow.status = "published"
    workflow.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(workflow)
    return workflow
