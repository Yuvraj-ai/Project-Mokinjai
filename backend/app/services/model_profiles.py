"""Resolve a model's context window from the installed LangChain profile data."""

_PROVIDER_SPEC = {
    "openai": "openai:{model_id}",
    "anthropic": "anthropic:{model_id}",
    "gemini": "google_genai:{model_id}",
}


def lookup_max_input_tokens(provider: str, model_id: str) -> int | None:
    """Return the profile window, or None when LangChain has no profile for this id."""
    template = _PROVIDER_SPEC.get(provider)
    if template is None or not model_id.strip():
        return None
    try:
        from langchain.chat_models import init_chat_model

        model = init_chat_model(template.format(model_id=model_id), api_key="profile-lookup")
        profile = getattr(model, "profile", None)
        if not isinstance(profile, dict):
            return None
        value = profile.get("max_input_tokens")
        return int(value) if value else None
    except Exception:
        return None


def default_compaction_tokens(context_window: int) -> int:
    return max(1, int(context_window * 0.8))
