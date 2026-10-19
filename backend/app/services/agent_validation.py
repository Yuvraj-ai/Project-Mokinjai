"""Validate the parts of an agent configuration that depend on the model.

The rules live here, not in the Pydantic schema, so the same code is used by the
API and by the runtime. A value the selected model does not support is refused,
never forwarded to the provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services.agent_capabilities import Capabilities, supported_parameters

MAX_STOP_SEQUENCES = 4
MAX_STOP_LENGTH = 200
WEB_SEARCH_METHODS = ("tavily", "exa", "native")


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


class AgentValidationError(Exception):
    def __init__(self, errors: list[FieldError]):
        self.errors = errors
        super().__init__("; ".join(f"{error.field}: {error.message}" for error in errors))


def normalise_params(raw: dict[str, Any] | None, capabilities: Capabilities) -> dict[str, Any]:
    """Return only the supported keys, with their values checked."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise AgentValidationError([FieldError("params", "must be an object")])

    allowed = set(supported_parameters(capabilities))
    errors: list[FieldError] = []
    result: dict[str, Any] = {}

    for key, value in raw.items():
        if value is None:
            continue
        field = f"params.{key}"
        if key not in allowed:
            errors.append(FieldError(field, "is not supported by the selected model"))
            continue

        if key == "temperature":
            if not _is_number(value):
                errors.append(FieldError(field, "must be a number"))
            elif not capabilities.temperature.minimum <= value <= capabilities.temperature.maximum:
                errors.append(
                    FieldError(
                        field,
                        "must be between "
                        f"{capabilities.temperature.minimum:g} and "
                        f"{capabilities.temperature.maximum:g}",
                    )
                )
            else:
                result[key] = float(value)

        elif key == "max_tokens":
            if not _is_int(value):
                errors.append(FieldError(field, "must be an integer"))
            elif not 1 <= value <= capabilities.max_output_tokens:
                errors.append(
                    FieldError(field, f"must be between 1 and {capabilities.max_output_tokens}")
                )
            else:
                result[key] = value

        elif key == "reasoning":
            if value not in capabilities.reasoning.levels:
                errors.append(
                    FieldError(field, "must be one of " + ", ".join(capabilities.reasoning.levels))
                )
            else:
                result[key] = value

        elif key == "streaming":
            if not isinstance(value, bool):
                errors.append(FieldError(field, "must be true or false"))
            else:
                result[key] = value

        elif key == "top_p":
            if not _is_number(value) or not 0 <= value <= 1:
                errors.append(FieldError(field, "must be between 0 and 1"))
            else:
                result[key] = float(value)

        elif key == "seed":
            if not _is_int(value):
                errors.append(FieldError(field, "must be an integer"))
            else:
                result[key] = value

        elif key == "stop":
            problem = _stop_problem(value)
            if problem:
                errors.append(FieldError(field, problem))
            else:
                result[key] = list(value)

    if errors:
        raise AgentValidationError(errors)
    return result


def normalise_web_search(
    raw: dict[str, Any] | None,
    capabilities: Capabilities,
    *,
    has_credential: Callable[[str], bool],
) -> dict[str, Any] | None:
    """Return the stored shape, or `None` when search is off."""
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise AgentValidationError([FieldError("web_search", "must be an object")])
    if not raw.get("enabled"):
        return None

    method = raw.get("method")
    if method not in WEB_SEARCH_METHODS:
        raise AgentValidationError(
            [FieldError("web_search", "choose Tavily, Exa or the provider's own search")]
        )
    if method in ("tavily", "exa") and not has_credential(method):
        raise AgentValidationError(
            [FieldError("web_search", f"add an API key for {method} first")]
        )
    if method == "native" and not capabilities.native_web_search:
        raise AgentValidationError(
            [FieldError("web_search", "the selected model has no built-in web search")]
        )
    return {"enabled": True, "method": method}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _stop_problem(value: Any) -> str | None:
    if not isinstance(value, list):
        return "must be a list of strings"
    if len(value) > MAX_STOP_SEQUENCES:
        return f"accepts at most {MAX_STOP_SEQUENCES} sequences"
    for entry in value:
        if not isinstance(entry, str) or not entry or len(entry) > MAX_STOP_LENGTH:
            return f"each sequence must be 1–{MAX_STOP_LENGTH} characters"
    return None
