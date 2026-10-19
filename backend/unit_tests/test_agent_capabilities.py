"""Slice 2: what the selected model actually supports.

Everything here is pure: profile data is passed in, so no test touches a provider.
The one function that would read LangChain metadata is exercised in
`test_agent_capabilities_lookup.py` with `init_chat_model` patched.
"""

import pytest

from app.services.agent_capabilities import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    capabilities_for,
    supported_parameters,
)
from app.services.model_profiles import lookup_profile


class TestProfileLookup:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        lookup_profile.cache_clear()
        yield
        lookup_profile.cache_clear()

    def test_empty_profile_when_langchain_raises(self, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("offline")

        monkeypatch.setattr("langchain.chat_models.init_chat_model", boom)
        assert lookup_profile("openai", "m") == {}

    def test_profile_is_read_from_the_model(self, monkeypatch):
        class FakeModel:
            profile = {"max_input_tokens": 100}

        monkeypatch.setattr("langchain.chat_models.init_chat_model", lambda *a, **k: FakeModel())
        assert lookup_profile("openai", "m")["max_input_tokens"] == 100

    def test_custom_and_blank_ids_skip_the_lookup(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "langchain.chat_models.init_chat_model", lambda *a, **k: calls.append(a)
        )
        assert lookup_profile("custom", "m") == {}
        assert lookup_profile("openai", "  ") == {}
        assert calls == []

    def test_capabilities_use_the_lookup_when_no_profile_is_given(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.agent_capabilities.lookup_profile",
            lambda provider, model_id: {"max_output_tokens": 777},
        )
        assert capabilities_for("openai", "m").max_output_tokens == 777


class TestMaxOutputTokens:
    def test_falls_back_when_the_profile_is_empty(self):
        caps = capabilities_for("openai", "unknown-model", profile={})
        assert caps.max_output_tokens == DEFAULT_MAX_OUTPUT_TOKENS
        assert caps.max_output_source == "fallback"

    def test_uses_the_langchain_profile(self):
        caps = capabilities_for("openai", "gpt-4o", profile={"max_output_tokens": 16384})
        assert caps.max_output_tokens == 16384
        assert caps.max_output_source == "model_profile"

    def test_an_explicit_override_wins(self):
        caps = capabilities_for(
            "openai",
            "gpt-4o",
            profile={"max_output_tokens": 16384},
            max_output_tokens_override=8000,
        )
        assert caps.max_output_tokens == 8000
        assert caps.max_output_source == "profile_override"

    def test_override_works_without_profile_data(self):
        caps = capabilities_for(
            "custom", "my-model", profile={}, max_output_tokens_override=1200
        )
        assert caps.max_output_tokens == 1200
        assert caps.max_output_source == "profile_override"

    def test_zero_or_negative_profile_values_are_ignored(self):
        caps = capabilities_for("openai", "x", profile={"max_output_tokens": 0})
        assert caps.max_output_tokens == DEFAULT_MAX_OUTPUT_TOKENS


class TestTemperature:
    @pytest.mark.parametrize(
        "provider,maximum",
        [("openai", 2.0), ("custom", 2.0), ("anthropic", 1.0), ("gemini", 2.0)],
    )
    def test_range_per_provider(self, provider, maximum):
        caps = capabilities_for(provider, "m", profile={})
        assert caps.temperature.supported is True
        assert caps.temperature.minimum == 0.0
        assert caps.temperature.maximum == maximum

    def test_a_model_that_refuses_temperature_hides_it(self):
        caps = capabilities_for("openai", "o3", profile={"temperature": False})
        assert caps.temperature.supported is False


class TestReasoning:
    def test_levels_are_read_from_the_profile(self):
        caps = capabilities_for(
            "openai",
            "gpt-5",
            profile={"reasoning_effort_levels": ["low", "medium", "high"]},
        )
        assert caps.reasoning.supported is True
        assert caps.reasoning.levels == ("low", "medium", "high")

    def test_only_the_three_ui_levels_are_offered(self):
        caps = capabilities_for(
            "openai",
            "gpt-5",
            profile={"reasoning_effort_levels": ["minimal", "low", "medium", "high"]},
        )
        assert caps.reasoning.levels == ("low", "medium", "high")

    def test_default_is_kept_when_it_is_offered(self):
        caps = capabilities_for(
            "openai",
            "gpt-5",
            profile={"reasoning_effort_levels": ["low", "high"], "reasoning_effort_default": "high"},
        )
        assert caps.reasoning.default == "high"

    def test_a_default_outside_the_offered_levels_is_dropped(self):
        caps = capabilities_for(
            "openai",
            "gpt-5",
            profile={"reasoning_effort_levels": ["low"], "reasoning_effort_default": "medium"},
        )
        assert caps.reasoning.default is None

    def test_no_levels_means_no_control(self):
        assert capabilities_for("anthropic", "claude", profile={}).reasoning.supported is False

    def test_custom_models_have_no_reasoning_control(self):
        caps = capabilities_for(
            "custom", "mine", profile={"reasoning_effort_levels": ["low", "high"]}
        )
        assert caps.reasoning.supported is False


class TestProviderCapabilities:
    @pytest.mark.parametrize(
        "provider,native",
        [("openai", True), ("anthropic", True), ("gemini", True), ("custom", False)],
    )
    def test_native_web_search(self, provider, native):
        assert capabilities_for(provider, "m", profile={}).native_web_search is native

    def test_advanced_parameters_are_provider_gated(self):
        openai = capabilities_for("openai", "m", profile={})
        anthropic = capabilities_for("anthropic", "m", profile={})
        gemini = capabilities_for("gemini", "m", profile={})

        assert (openai.advanced.top_p, openai.advanced.seed, openai.advanced.stop) == (True, True, True)
        assert (anthropic.advanced.top_p, anthropic.advanced.seed, anthropic.advanced.stop) == (
            True,
            False,
            True,
        )
        assert (gemini.advanced.top_p, gemini.advanced.seed, gemini.advanced.stop) == (True, True, True)

    def test_capabilities_serialise_for_the_options_endpoint(self):
        payload = capabilities_for("openai", "gpt-5", profile={"max_output_tokens": 1024}).as_dict()
        assert payload["max_output_tokens"] == 1024
        assert payload["temperature"] == {"supported": True, "minimum": 0.0, "maximum": 2.0}
        assert payload["advanced"]["seed"] is True

    def test_unknown_provider_is_a_programming_error(self):
        with pytest.raises(ValueError):
            capabilities_for("cohere", "m", profile={})

    def test_supported_parameters_names_every_exposed_control(self):
        caps = capabilities_for(
            "openai",
            "gpt-5",
            profile={"reasoning_effort_levels": ["low", "medium", "high"]},
        )
        assert supported_parameters(caps) == [
            "temperature",
            "max_tokens",
            "reasoning",
            "streaming",
            "top_p",
            "seed",
            "stop",
        ]

    def test_supported_parameters_omits_what_the_model_refuses(self):
        caps = capabilities_for(
            "anthropic", "claude", profile={"temperature": False, "reasoning_effort_levels": []}
        )
        assert supported_parameters(caps) == ["max_tokens", "streaming", "top_p", "stop"]
