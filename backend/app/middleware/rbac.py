from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.middleware.auth import get_current_user
from app.utils.errors import ForbiddenException, NotFoundException

ROLE_HIERARCHY = {"owner": 4, "admin": 3, "editor": 2, "viewer": 1}


def require_workspace_role(min_role: str = "viewer"):
    async def dependency(
        workspace_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        member = result.scalar_one_or_none()

        if member is None:
            raise NotFoundException("Workspace")

        min_level = ROLE_HIERARCHY.get(min_role, 0)
        user_level = ROLE_HIERARCHY.get(member.role, 0)

        if user_level < min_level:
            raise ForbiddenException("Insufficient permissions for this workspace")

        return member

    return dependency
