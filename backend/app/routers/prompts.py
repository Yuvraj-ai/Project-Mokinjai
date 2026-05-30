from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.logging import logger
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.models.prompt import PromptTemplate
from app.schemas.prompt import (
    PromptCreate,
    PromptUpdate,
    PromptResponse,
    PromptListResponse,
)
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.utils.errors import NotFoundException

router = APIRouter()


@router.post("", response_model=PromptResponse)
async def create_prompt(
    workspace_id: str,
    request: PromptCreate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    prompt = PromptTemplate(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        content=request.content,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(
        select(func.count()).select_from(PromptTemplate).where(PromptTemplate.workspace_id == workspace_id)
    )
    total = count_result.scalar()

    result = await db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.workspace_id == workspace_id)
        .order_by(PromptTemplate.updated_at.desc())
    )
    prompts = result.scalars().all()
    return PromptListResponse(prompts=prompts, total=total)


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    workspace_id: str,
    prompt_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.id == prompt_id,
            PromptTemplate.workspace_id == workspace_id,
        )
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundException("Prompt")
    return prompt


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    workspace_id: str,
    prompt_id: str,
    request: PromptUpdate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.id == prompt_id,
            PromptTemplate.workspace_id == workspace_id,
        )
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundException("Prompt")

    if request.name is not None:
        prompt.name = request.name
    if request.description is not None:
        prompt.description = request.description
    if request.content is not None:
        prompt.content = request.content

    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.delete("/{prompt_id}")
async def delete_prompt(
    workspace_id: str,
    prompt_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.id == prompt_id,
            PromptTemplate.workspace_id == workspace_id,
        )
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundException("Prompt")

    await db.delete(prompt)
    await db.commit()
    return {"success": True}
