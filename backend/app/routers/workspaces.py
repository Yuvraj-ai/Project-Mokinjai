from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    MemberAdd,
    MemberResponse,
)
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.utils.errors import NotFoundException, ForbiddenException, BadRequestException

router = APIRouter()


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    request: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = Workspace(name=request.name, owner_id=current_user.id)
    db.add(workspace)
    await db.flush()

    # Add creator as owner member
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(member)
    await db.commit()
    await db.refresh(workspace)

    return workspace


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
    )
    return result.scalars().all()


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise NotFoundException("Workspace")
    return workspace


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    request: WorkspaceUpdate,
    _member: WorkspaceMember = Depends(require_workspace_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise NotFoundException("Workspace")

    if request.name is not None:
        workspace.name = request.name

    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise NotFoundException("Workspace")

    await db.delete(workspace)
    await db.commit()
    return {"success": True}


@router.post("/{workspace_id}/members", response_model=MemberResponse)
async def add_member(
    workspace_id: str,
    request: MemberAdd,
    _member: WorkspaceMember = Depends(require_workspace_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    # Check user exists
    result = await db.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundException("User")

    # Check not already a member
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
        raise ForbiddenException("Cannot remove workspace owner")

    await db.delete(member)
    await db.commit()
    return {"success": True}
