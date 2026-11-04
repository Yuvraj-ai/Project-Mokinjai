from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from app.database import get_db
from app.logging import logger
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.agent import AgentDocument
from app.models.knowledge import Document
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    MemberAdd,
    MemberResponse,
)
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.services.storage import StorageError, get_storage
from app.utils.errors import NotFoundException, ForbiddenException, BadRequestException

router = APIRouter()


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    request: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"User {current_user.id} creating workspace '{request.name}'")
    workspace = Workspace(name=request.name, owner_id=current_user.id)
    db.add(workspace)
    await db.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(member)
    await db.commit()
    await db.refresh(workspace)

    logger.info(f"Workspace {workspace.id} created by user {current_user.id}")
    return workspace


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"User {current_user.id} listing workspaces")
    result = await db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
    )
    rows = result.all()
    return [
        WorkspaceResponse.model_validate(workspace).model_copy(update={"role": role})
        for workspace, role in rows
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        logger.warning(f"Workspace {workspace_id} not found")
        raise NotFoundException("Workspace")
    response = WorkspaceResponse.model_validate(workspace)
    response.role = member.role
    return response


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    request: WorkspaceUpdate,
    _member: WorkspaceMember = Depends(require_workspace_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Updating workspace {workspace_id}")
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        logger.warning(f"Workspace {workspace_id} not found")
        raise NotFoundException("Workspace")

    if request.name is not None:
        workspace.name = request.name

    await db.commit()
    await db.refresh(workspace)
    logger.info(f"Workspace {workspace_id} updated")
    return workspace


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Deleting workspace {workspace_id}")
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        logger.warning(f"Workspace {workspace_id} not found")
        raise NotFoundException("Workspace")

    # The folder FK is RESTRICT, so the rows must go before the workspace cascade can
    # remove the folders. Keys are read first because the rows are gone after the commit.
    keys = [
        key
        for key in (
            await db.execute(
                select(Document.file_url).where(Document.workspace_id == workspace_id)
            )
        ).scalars()
        if key
    ]
    document_ids = select(Document.id).where(Document.workspace_id == workspace_id)
    await db.execute(delete(AgentDocument).where(AgentDocument.document_id.in_(document_ids)))
    await db.execute(delete(Document).where(Document.workspace_id == workspace_id))

    await db.delete(workspace)
    await db.commit()

    for key in keys:
        try:
            await get_storage().delete_file(key)
        except StorageError:
            logger.exception(f"Orphaned object left behind at {key!r}")

    logger.info(f"Workspace {workspace_id} deleted")
    return {"success": True}


@router.post("/{workspace_id}/members", response_model=MemberResponse)
async def add_member(
    workspace_id: str,
    request: MemberAdd,
    _member: WorkspaceMember = Depends(require_workspace_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Adding user {request.user_id} as {request.role} to workspace {workspace_id}")
    result = await db.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        logger.warning(f"User {request.user_id} not found")
        raise NotFoundException("User")

    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == request.user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise BadRequestException("User is already a member")

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=request.user_id,
        role=request.role,
    )
    db.add(member)
    await db.commit()
    logger.info(f"User {request.user_id} added to workspace {workspace_id}")
    return MemberResponse(
        workspace_id=workspace_id,
        user_id=request.user_id,
        role=request.role,
        user_email=user.email,
        user_name=user.name,
    )


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
async def list_members(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"Listing members for workspace {workspace_id}")
    result = await db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
    )
    rows = result.all()
    return [
        MemberResponse(
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            role=m.role,
            user_email=u.email,
            user_name=u.name,
        )
        for m, u in rows
    ]


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: str,
    user_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Removing user {user_id} from workspace {workspace_id}")
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise NotFoundException("Member")
    if member.role == "owner":
        logger.warning(f"Attempted to remove owner from workspace {workspace_id}")
        raise ForbiddenException("Cannot remove workspace owner")

    await db.delete(member)
    await db.commit()
    logger.info(f"User {user_id} removed from workspace {workspace_id}")
    return {"success": True}
