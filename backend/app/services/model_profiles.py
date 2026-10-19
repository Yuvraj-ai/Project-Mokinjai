"""Resolve model metadata from the installed LangChain profile data."""

from functools import lru_cache

_PROVIDER_SPEC = {
    "openai": "openai:{model_id}",
    "anthropic": "anthropic:{model_id}",
    "gemini": "google_genai:{model_id}",
}


@lru_cache(maxsize=256)
def lookup_profile(provider: str, model_id: str) -> dict:
    """Return LangChain's profile dict, or an empty dict when none is known.

    Cached per process: constructing a model is cheap but reading its profile can
    reach models.dev, and the same few models are asked about on every form load.
    """
    template = _PROVIDER_SPEC.get(provider)
    if template is None or not model_id.strip():
        return {}
    try:
        from langchain.chat_models import init_chat_model

        model = init_chat_model(template.format(model_id=model_id), api_key="profile-lookup")
        profile = getattr(model, "profile", None)
        return dict(profile) if isinstance(profile, dict) else {}
    except Exception:
        return {}


def lookup_max_input_tokens(provider: str, model_id: str) -> int | None:
    """Return the profile window, or None when LangChain has no profile for this id."""
    value = lookup_profile(provider, model_id).get("max_input_tokens")
    return int(value) if value else None


def default_compaction_tokens(context_window: int) -> int:
    return max(1, int(context_window * 0.8))
