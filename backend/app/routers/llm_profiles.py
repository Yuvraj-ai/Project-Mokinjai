from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt_api_key, encrypt_api_key
from app.database import get_db
from app.logging import logger
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.llm_profile import LlmProfile
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.llm_profile import (
    ContextWindowLookup,
    LlmProfileListResponse,
    LlmProfileResponse,
    LlmProfileTestRequest,
)
from app.services.llm_probe import LlmProbeError, probe_llm
from app.services.model_profiles import default_compaction_tokens, lookup_max_input_tokens
from app.utils.errors import BadRequestException, NotFoundException

router = APIRouter()


def _to_response(profile: LlmProfile) -> LlmProfileResponse:
    return LlmProfileResponse(
        id=profile.id,
        workspace_id=profile.workspace_id,
        name=profile.name,
        provider=profile.provider,
        model_id=profile.model_id,
        base_url=profile.base_url,
        context_window=profile.context_window,
        compaction_at_tokens=profile.compaction_at_tokens,
        input_price_per_million=profile.input_price_per_million,
        output_price_per_million=profile.output_price_per_million,
        cache_price_per_million=profile.cache_price_per_million,
        status=profile.status,
        last_error=profile.last_error,
        has_api_key=True,
        usable=profile.status == "verified",
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _resolve_window(provider: str, model_id: str, supplied: int | None) -> int:
    known = lookup_max_input_tokens(provider, model_id)
    if known is not None:
        return known
    if supplied is None:
        raise BadRequestException(
            "Context window is required. This model id is not in the LangChain profile."
        )
    return supplied


async def _load_profile(db: AsyncSession, workspace_id: str, profile_id: str) -> LlmProfile:
    result = await db.execute(
        select(LlmProfile).where(
            LlmProfile.id == profile_id,
            LlmProfile.workspace_id == workspace_id,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise NotFoundException("LLM profile")
    return profile


async def _run_test(
    db: AsyncSession,
    workspace_id: str,
    request: LlmProfileTestRequest,
    existing: LlmProfile | None,
) -> LlmProfileResponse:
    if request.provider == "custom" and not (request.base_url and request.base_url.strip()):
        raise BadRequestException("Custom providers require a base URL")

    context_window = _resolve_window(request.provider, request.model_id, request.context_window)
    compaction = request.compaction_at_tokens or default_compaction_tokens(context_window)
    if compaction > context_window:
        raise BadRequestException("Compaction threshold cannot exceed the context window")

    api_key = request.api_key.strip()
    if not api_key:
        if existing is None:
            raise BadRequestException("API key is required")
        api_key = decrypt_api_key(existing.encrypted_api_key)

    try:
        await probe_llm(
            provider=request.provider,
            model_id=request.model_id,
            api_key=api_key,
            base_url=request.base_url,
        )
        status = "verified"
        last_error = None
    except LlmProbeError as exc:
        status = "failed"
        last_error = str(exc)

    ciphertext = encrypt_api_key(api_key)
    profile = existing or LlmProfile(workspace_id=workspace_id)
    profile.name = request.name
    profile.provider = request.provider
    profile.model_id = request.model_id
    profile.base_url = request.base_url.strip() if request.base_url else None
    profile.encrypted_api_key = ciphertext
    profile.context_window = context_window
    profile.compaction_at_tokens = compaction
    profile.input_price_per_million = request.input_price_per_million
    profile.output_price_per_million = request.output_price_per_million
    profile.cache_price_per_million = request.cache_price_per_million
    profile.status = status
    profile.last_error = last_error
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    logger.info(f"LLM profile {profile.id} saved with status {status}")
    return _to_response(profile)


@router.get("/context-window", response_model=ContextWindowLookup)
async def lookup_context_window(
    provider: str,
    model_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
):
    window = lookup_max_input_tokens(provider, model_id)
    return ContextWindowLookup(known=window is not None, max_input_tokens=window)


@router.get("", response_model=LlmProfileListResponse)
async def list_llm_profiles(
    workspace_id: str,
    usable: bool = Query(False),
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    filters = [LlmProfile.workspace_id == workspace_id]
    if usable:
        filters.append(LlmProfile.status == "verified")
    count_result = await db.execute(select(func.count()).select_from(LlmProfile).where(*filters))
    total = count_result.scalar_one()
    result = await db.execute(
        select(LlmProfile).where(*filters).order_by(LlmProfile.created_at.desc())
    )
    profiles = [_to_response(row) for row in result.scalars().all()]
    return LlmProfileListResponse(profiles=profiles, total=total)


@router.post("/test", response_model=LlmProfileResponse)
async def test_new_llm_profile(
    workspace_id: str,
    request: LlmProfileTestRequest,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    existing = None
    if request.profile_id:
        existing = await _load_profile(db, workspace_id, request.profile_id)
    logger.info(f"Testing LLM profile '{request.name}' for user {current_user.id}")
    return await _run_test(db, workspace_id, request, existing)


@router.post("/{profile_id}/test", response_model=LlmProfileResponse)
async def retest_llm_profile(
    workspace_id: str,
    profile_id: str,
    request: LlmProfileTestRequest,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    existing = await _load_profile(db, workspace_id, profile_id)
    logger.info(f"Retesting LLM profile {profile_id} for user {current_user.id}")
    return await _run_test(db, workspace_id, request, existing)


@router.delete("/{profile_id}")
async def delete_llm_profile(
    workspace_id: str,
    profile_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    profile = await _load_profile(db, workspace_id, profile_id)
    await db.delete(profile)
    await db.commit()
    return {"success": True}
