"""What the selected model actually supports, from LangChain's model profile.

LangChain exposes `model.profile` (powered by models.dev) with the fields this
feature needs: `max_output_tokens`, `temperature`, `reasoning_effort_levels`,
`structured_output` and `tool_calling`. It does not expose a temperature range or
which of `top_p`/`seed`/`stop` a provider accepts, so those are a small documented
provider matrix. Everything here is pure; `lookup_profile` is the only function
that touches LangChain.
"""

from dataclasses import dataclass
from typing import Any

from app.services.model_profiles import lookup_profile

DEFAULT_MAX_OUTPUT_TOKENS = 4096
"""Universal completion ceiling when neither the app nor LangChain knows better."""

PROVIDERS = ("openai", "anthropic", "gemini", "custom")

_TEMPERATURE_MAX = {"openai": 2.0, "custom": 2.0, "anthropic": 1.0, "gemini": 2.0}
_NATIVE_WEB_SEARCH = {"openai": True, "anthropic": True, "gemini": True, "custom": False}
_SEED_SUPPORTED = {"openai": True, "custom": True, "anthropic": False, "gemini": True}
_UI_REASONING_LEVELS = ("low", "medium", "high")


@dataclass(frozen=True)
class TemperatureCapability:
    supported: bool
    minimum: float
    maximum: float


@dataclass(frozen=True)
class ReasoningCapability:
    supported: bool
    levels: tuple[str, ...]
    default: str | None


@dataclass(frozen=True)
class AdvancedCapability:
    top_p: bool
    seed: bool
    stop: bool


@dataclass(frozen=True)
class Capabilities:
    provider: str
    model_id: str
    max_output_tokens: int
    max_output_source: str  # profile_override | model_profile | fallback
    temperature: TemperatureCapability
    reasoning: ReasoningCapability
    advanced: AdvancedCapability
    native_web_search: bool
    structured_output: bool
    tool_calling: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "max_output_tokens": self.max_output_tokens,
            "max_output_source": self.max_output_source,
            "temperature": {
                "supported": self.temperature.supported,
                "minimum": self.temperature.minimum,
                "maximum": self.temperature.maximum,
            },
            "reasoning": {
                "supported": self.reasoning.supported,
                "levels": list(self.reasoning.levels),
                "default": self.reasoning.default,
            },
            "advanced": {
                "top_p": self.advanced.top_p,
                "seed": self.advanced.seed,
                "stop": self.advanced.stop,
            },
            "native_web_search": self.native_web_search,
            "structured_output": self.structured_output,
            "tool_calling": self.tool_calling,
        }


def capabilities_for(
    provider: str,
    model_id: str,
    *,
    profile: dict[str, Any] | None = None,
    max_output_tokens_override: int | None = None,
) -> Capabilities:
    """Resolve the controls the UI may show for one model.

    `profile` is injectable so tests and callers with cached metadata never touch
    the network. When omitted, LangChain's profile is looked up.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider: {provider!r}")

    data = lookup_profile(provider, model_id) if profile is None else profile

    ceiling, source = _resolve_output_ceiling(data, max_output_tokens_override)
    levels = _reasoning_levels(provider, data)
    default = data.get("reasoning_effort_default")
    if default not in levels:
        default = None

    return Capabilities(
        provider=provider,
        model_id=model_id,
        max_output_tokens=ceiling,
        max_output_source=source,
        temperature=TemperatureCapability(
            supported=bool(data.get("temperature", True)),
            minimum=0.0,
            maximum=_TEMPERATURE_MAX[provider],
        ),
        reasoning=ReasoningCapability(
            supported=bool(levels),
            levels=levels,
            default=default,
        ),
        advanced=AdvancedCapability(
            top_p=True,
            seed=_SEED_SUPPORTED[provider],
            stop=True,
        ),
        native_web_search=_NATIVE_WEB_SEARCH[provider],
        structured_output=bool(data.get("structured_output", True)),
        tool_calling=bool(data.get("tool_calling", True)),
    )


def supported_parameters(capabilities: Capabilities) -> list[str]:
    """The parameter names this model accepts, in UI order."""
    names: list[str] = []
    if capabilities.temperature.supported:
        names.append("temperature")
    names.append("max_tokens")
    if capabilities.reasoning.supported:
        names.append("reasoning")
    names.append("streaming")
    if capabilities.advanced.top_p:
        names.append("top_p")
    if capabilities.advanced.seed:
        names.append("seed")
    if capabilities.advanced.stop:
        names.append("stop")
    return names


def _resolve_output_ceiling(
    profile: dict[str, Any], override: int | None
) -> tuple[int, str]:
    if override is not None and override > 0:
        return override, "profile_override"
    value = profile.get("max_output_tokens")
    if isinstance(value, int) and value > 0:
        return value, "model_profile"
    return DEFAULT_MAX_OUTPUT_TOKENS, "fallback"


def _reasoning_levels(provider: str, profile: dict[str, Any]) -> tuple[str, ...]:
    if provider == "custom":
        # An OpenAI-compatible endpoint gives no evidence that it understands
        # provider-specific reasoning kwargs; showing the control would lie.
        return ()
    raw = profile.get("reasoning_effort_levels")
    if not isinstance(raw, (list, tuple)):
        return ()
    offered = {str(level).lower() for level in raw}
    return tuple(level for level in _UI_REASONING_LEVELS if level in offered)
