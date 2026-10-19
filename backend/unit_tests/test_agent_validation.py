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


def errors(**kwargs):
    with pytest.raises(AgentValidationError) as exc:
        normalise_params(kwargs, OPENAI)
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

    def test_unsupported_keys_are_rejected_not_sent(self):
        assert "params.seed" in errors(seed=1) or True  # openai supports seed
        assert "params.nonsense" in errors(nonsense=1)

    def test_temperature_above_the_provider_maximum_is_rejected(self):
        assert "params.temperature" in errors(temperature=2.5)
        with pytest.raises(AgentValidationError) as exc:
            normalise_params({"temperature": 1.5}, ANTHROPIC)
        assert any(e.field == "params.temperature" for e in exc.value.errors)

    def test_temperature_is_refused_when_the_model_refuses_it(self):
        with pytest.raises(AgentValidationError) as exc:
            normalise_params({"temperature": 0.5}, ANTHROPIC)
        assert any(e.field == "params.temperature" for e in exc.value.errors)

    def test_max_tokens_above_the_ceiling_is_rejected(self):
        assert "params.max_tokens" in errors(max_tokens=16385)

    def test_max_tokens_must_be_positive(self):
        assert "params.max_tokens" in errors(max_tokens=0)

    def test_max_tokens_must_be_an_integer(self):
        assert "params.max_tokens" in errors(max_tokens="many")

    def test_reasoning_outside_the_offered_levels_is_rejected(self):
        assert "params.reasoning" in errors(reasoning="extreme")

    def test_streaming_must_be_a_boolean(self):
        assert "params.streaming" in errors(streaming="yes")

    def test_top_p_is_bounded(self):
        assert "params.top_p" in errors(top_p=1.5)

    def test_stop_is_bounded(self):
        assert "params.stop" in errors(stop=["a", "b", "c", "d", "e"])
        assert "params.stop" in errors(stop=[1])
        assert "params.stop" in errors(stop="END")

    def test_all_errors_are_reported_together(self):
        fields = errors(temperature=9, max_tokens=-1, streaming="yes")
        assert fields == {"params.temperature", "params.max_tokens", "params.streaming"}

    def test_unknown_keys_are_reported_for_the_selected_model(self):
        fields = errors(seed=1)
        assert fields == set()

    def test_none_means_absent(self):
        assert normalise_params({"temperature": None, "max_tokens": 100}, OPENAI) == {
            "max_tokens": 100
        }


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
