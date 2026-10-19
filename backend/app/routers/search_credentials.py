from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import encrypt_api_key
from app.database import get_db
from app.middleware.rbac import require_workspace_role
from app.models.search_credential import SearchCredential
from app.models.workspace import WorkspaceMember
from app.schemas.search_credential import (
    SearchCredentialResponse,
    SearchCredentialUpsert,
    SearchProvider,
)

router = APIRouter()

PROVIDERS: tuple[str, ...] = ("tavily", "exa")


async def _row(db: AsyncSession, workspace_id: str, provider: str) -> SearchCredential | None:
    return (
        await db.execute(
            select(SearchCredential).where(
                SearchCredential.workspace_id == workspace_id,
                SearchCredential.provider == provider,
            )
        )
    ).scalar_one_or_none()


@router.get("", response_model=list[SearchCredentialResponse])
async def list_search_credentials(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    stored = set(
        (
            await db.execute(
                select(SearchCredential.provider).where(
                    SearchCredential.workspace_id == workspace_id
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        SearchCredentialResponse(provider=provider, has_key=provider in stored)
        for provider in PROVIDERS
    ]


@router.put("/{provider}", response_model=SearchCredentialResponse)
async def upsert_search_credential(
    workspace_id: str,
    provider: SearchProvider,
    request: SearchCredentialUpsert,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _row(db, workspace_id, provider)
    ciphertext = encrypt_api_key(request.api_key.strip())
    if row is None:
        db.add(
            SearchCredential(
                workspace_id=workspace_id,
                provider=provider,
                encrypted_api_key=ciphertext,
            )
        )
    else:
        row.encrypted_api_key = ciphertext
    await db.commit()
    return SearchCredentialResponse(provider=provider, has_key=True)


@router.delete("/{provider}", status_code=204)
async def delete_search_credential(
    workspace_id: str,
    provider: SearchProvider,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _row(db, workspace_id, provider)
    if row is not None:
        await db.delete(row)
        await db.commit()
    return Response(status_code=204)
