from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.logging import logger
from app.models.workspace import WorkspaceMember
from app.models.knowledge import KnowledgeBase
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.middleware.rbac import require_workspace_role
from app.utils.errors import BadRequestException, NotFoundException

router = APIRouter()

# Only "document" is supported: a url knowledge base implies fetching and crawling, and
# an api knowledge base has no design at all. The set lives here rather than in a database
# constraint so widening it later needs no migration.
SUPPORTED_KNOWLEDGE_BASE_TYPES = ("document",)


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    workspace_id: str,
    request: KnowledgeBaseCreate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    if request.type not in SUPPORTED_KNOWLEDGE_BASE_TYPES:
        raise BadRequestException(
            f"Unsupported knowledge base type {request.type!r}. Only "
            f"{', '.join(repr(t) for t in SUPPORTED_KNOWLEDGE_BASE_TYPES)} is supported; "
            "'url' and 'api' have no design yet."
        )
    logger.info(f"Creating knowledge base '{request.name}' in workspace {workspace_id}")
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
    logger.info(f"Knowledge base {kb.id} created")
    return kb


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"Listing knowledge bases for workspace {workspace_id}")
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.workspace_id == workspace_id)
        .order_by(KnowledgeBase.created_at.desc())
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
        logger.warning(f"Knowledge base {kb_id} not found in workspace {workspace_id}")
        raise NotFoundException("Knowledge base")
    return kb


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    workspace_id: str,
    kb_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Deleting knowledge base {kb_id}")
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.workspace_id == workspace_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        logger.warning(f"Knowledge base {kb_id} not found")
        raise NotFoundException("Knowledge base")

    await db.delete(kb)
    await db.commit()
    logger.info(f"Knowledge base {kb_id} deleted")
    return {"success": True}
