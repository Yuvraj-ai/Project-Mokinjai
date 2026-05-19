from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.middleware.auth import get_current_user
from app.utils.errors import ForbiddenException

ROLE_HIERARCHY = {"owner": 4, "admin": 3, "editor": 2, "viewer": 1}


def require_workspace_role(min_role: str = "viewer"):
    if min_role not in ROLE_HIERARCHY:
        raise ValueError(f"Unknown workspace role: {min_role}")

    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        workspace_id = request.path_params.get("workspace_id")
        if not workspace_id:
            raise RuntimeError("require_workspace_role requires a {workspace_id} path parameter")

        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        member = result.scalar_one_or_none()

        if member is None:
            raise ForbiddenException("You do not have access to this workspace")

        min_level = ROLE_HIERARCHY.get(min_role)
        user_level = ROLE_HIERARCHY.get(member.role, 0)

        if user_level < min_level:
            raise ForbiddenException("Insufficient permissions for this workspace")

        return member

    return dependency
