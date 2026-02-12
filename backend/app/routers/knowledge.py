from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.workspace import WorkspaceMember
from app.models.knowledge import KnowledgeBase
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.middleware.rbac import require_workspace_role
from app.utils.errors import NotFoundException

router = APIRouter()


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    workspace_id: str,
    request: KnowledgeBaseCreate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    kb = KnowledgeBase(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        type=request.type,
        config=request.config,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.workspace_id == workspace_id)
    )
    return result.scalars().all()


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    workspace_id: str,
    kb_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.workspace_id == workspace_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundException("Knowledge base")
    return kb


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    workspace_id: str,
    kb_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.workspace_id == workspace_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundException("Knowledge base")

    await db.delete(kb)
    await db.commit()
    return {"success": True}
