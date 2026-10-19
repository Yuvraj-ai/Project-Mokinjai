"""Slice 4: parameter and web-search validation, authoritative on the server."""

import pytest

from app.services.agent_capabilities import capabilities_for
from app.services.agent_validation import (
    AgentValidationError,
    normalise_params,
    normalise_web_search,
)

OPENAI = capabilities_for(
    "openai",
    "gpt-5",
    profile={
        "max_output_tokens": 16384,
        "reasoning_effort_levels": ["low", "medium", "high"],
    },
)
ANTHROPIC = capabilities_for(
    "anthropic", "claude", profile={"max_output_tokens": 8192, "temperature": False}
)


def fields_for(payload, capabilities=OPENAI):
    with pytest.raises(AgentValidationError) as exc:
        normalise_params(payload, capabilities)
    return {error.field for error in exc.value.errors}


class TestParams:
    def test_a_valid_payload_is_normalised(self):
        result = normalise_params(
            {
                "temperature": 0.4,
                "max_tokens": 2048,
                "reasoning": "high",
                "streaming": True,
                "top_p": 0.9,
                "seed": 7,
                "stop": ["END"],
            },
            OPENAI,
        )
        assert result == {
            "temperature": 0.4,
            "max_tokens": 2048,
            "reasoning": "high",
            "streaming": True,
            "top_p": 0.9,
            "seed": 7,
            "stop": ["END"],
        }

    def test_supported_advanced_keys_pass(self):
        assert normalise_params({"seed": 1}, OPENAI) == {"seed": 1}

    def test_unsupported_keys_are_rejected_not_sent(self):
        assert "params.nonsense" in fields_for({"nonsense": 1})

    def test_provider_gated_keys_are_rejected(self):
        assert "params.seed" in fields_for({"seed": 1}, ANTHROPIC)

    def test_temperature_above_the_provider_maximum_is_rejected(self):
        assert "params.temperature" in fields_for({"temperature": 2.5})
        assert "params.temperature" in fields_for({"temperature": 1.5}, ANTHROPIC)

    def test_temperature_is_refused_when_the_model_refuses_it(self):
        assert "params.temperature" in fields_for({"temperature": 0.5}, ANTHROPIC)

    def test_max_tokens_above_the_ceiling_is_rejected(self):
        assert "params.max_tokens" in fields_for({"max_tokens": 16385})

    def test_max_tokens_must_be_positive(self):
        assert "params.max_tokens" in fields_for({"max_tokens": 0})

    def test_max_tokens_must_be_an_integer(self):
        assert "params.max_tokens" in fields_for({"max_tokens": "many"})
        assert "params.max_tokens" in fields_for({"max_tokens": True})

    def test_reasoning_outside_the_offered_levels_is_rejected(self):
        assert "params.reasoning" in fields_for({"reasoning": "extreme"})

    def test_reasoning_is_refused_when_the_model_has_no_levels(self):
        assert "params.reasoning" in fields_for({"reasoning": "low"}, ANTHROPIC)

    def test_streaming_must_be_a_boolean(self):
        assert "params.streaming" in fields_for({"streaming": "yes"})

    def test_top_p_is_bounded(self):
        assert "params.top_p" in fields_for({"top_p": 1.5})
        assert "params.top_p" in fields_for({"top_p": -0.1})

    def test_stop_is_bounded(self):
        assert "params.stop" in fields_for({"stop": ["a", "b", "c", "d", "e"]})
        assert "params.stop" in fields_for({"stop": [1]})
        assert "params.stop" in fields_for({"stop": "END"})

    def test_all_errors_are_reported_together(self):
        fields = fields_for({"temperature": 9, "max_tokens": -1, "streaming": "yes"})
        assert fields == {"params.temperature", "params.max_tokens", "params.streaming"}

    def test_none_means_absent(self):
        assert normalise_params({"temperature": None, "max_tokens": 100}, OPENAI) == {
            "max_tokens": 100
        }

    def test_empty_params_are_valid(self):
        assert normalise_params({}, OPENAI) == {}


class TestWebSearch:
    def test_disabled_is_none(self):
        assert normalise_web_search({"enabled": False}, OPENAI, has_credential=lambda p: True) is None
        assert normalise_web_search(None, OPENAI, has_credential=lambda p: True) is None

    def test_tavily_requires_a_credential(self):
        with pytest.raises(AgentValidationError) as exc:
            normalise_web_search(
                {"enabled": True, "method": "tavily"}, OPENAI, has_credential=lambda p: False
            )
        assert any(e.field == "web_search" for e in exc.value.errors)

    def test_tavily_is_accepted_with_a_credential(self):
        result = normalise_web_search(
            {"enabled": True, "method": "tavily"}, OPENAI, has_credential=lambda p: True
        )
        assert result == {"enabled": True, "method": "tavily"}

    def test_exa_is_accepted_with_a_credential(self):
        result = normalise_web_search(
            {"enabled": True, "method": "exa"}, OPENAI, has_credential=lambda p: True
        )
        assert result == {"enabled": True, "method": "exa"}

    def test_native_is_refused_when_the_provider_cannot(self):
        custom = capabilities_for("custom", "m", profile={})
        with pytest.raises(AgentValidationError):
            normalise_web_search(
                {"enabled": True, "method": "native"}, custom, has_credential=lambda p: True
            )

    def test_native_is_accepted_for_a_supporting_provider(self):
        result = normalise_web_search(
            {"enabled": True, "method": "native"}, OPENAI, has_credential=lambda p: True
        )
        assert result == {"enabled": True, "method": "native"}

    def test_an_unknown_method_is_refused(self):
        with pytest.raises(AgentValidationError):
            normalise_web_search(
                {"enabled": True, "method": "google-scrape"}, OPENAI, has_credential=lambda p: True
            )
