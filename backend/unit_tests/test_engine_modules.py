import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.engine.context import ExecutionContext
from app.engine.modules.registry import ModuleRegistry, InputModule
from app.engine.modules.prompt import PromptModule
from app.engine.modules.output import OutputModule
from app.engine.modules.conditional import ConditionalModule
from app.engine.modules.transform import TransformModule
from app.engine.modules.http_request import HttpRequestModule
from app.engine.modules.agent import AgentModule


class TestModuleRegistry:
    def test_get_known_module(self):
        mod = ModuleRegistry.get_module("input")
        assert isinstance(mod, InputModule)

    def test_get_all_known_types(self):
        types = ModuleRegistry.list_types()
        assert "input" in types
        assert "agent" in types
        assert "prompt" in types
        assert "output" in types
        assert "conditional" in types
        assert "transform" in types
        assert "http_request" in types

    def test_get_unknown_module_raises(self):
        with pytest.raises(ValueError, match="Unknown module type"):
            ModuleRegistry.get_module("nonexistent")

    def test_register_custom_module(self):
        class CustomModule(InputModule):
            module_type = "custom"

        ModuleRegistry.register("custom", CustomModule)
        mod = ModuleRegistry.get_module("custom")
        assert isinstance(mod, CustomModule)
        # cleanup
        del ModuleRegistry._modules["custom"]


class TestInputModule:
    @pytest.mark.asyncio
    async def test_input_module_passthrough(self):
        mod = InputModule()
        ctx = ExecutionContext({"message": "hello"})
        result = await mod.execute({}, {}, ctx)
        assert result == {"output": {"message": "hello"}}

    @pytest.mark.asyncio
    async def test_input_module_with_parent_input(self):
        mod = InputModule()
        ctx = ExecutionContext()
        result = await mod.execute({}, {"input": "from parent"}, ctx)
        assert result == {"output": "from parent"}


class TestPromptModule:
    @pytest.mark.asyncio
    async def test_prompt_replaces_variables(self):
        mod = PromptModule()
        ctx = ExecutionContext()
        config = {"template": "Hello {{name}}, your message is {{msg}}"}
        inputs = {"input": "irrelevant", "name": "Alice", "msg": "hi"}
        result = await mod.execute(config, inputs, ctx)
        assert result["output"] == "Hello Alice, your message is hi"
        assert result["prompt"] == "Hello Alice, your message is hi"

    @pytest.mark.asyncio
    async def test_prompt_with_config_variables(self):
        mod = PromptModule()
        ctx = ExecutionContext()
        config = {
            "template": "You are {{role}}",
            "variables": {"role": "assistant"},
        }
        result = await mod.execute(config, {}, ctx)
        assert result["output"] == "You are assistant"

    @pytest.mark.asyncio
    async def test_prompt_unknown_variable_kept(self):
        mod = PromptModule()
        ctx = ExecutionContext()
        config = {"template": "Hello {{unknown}}"}
        result = await mod.execute(config, {}, ctx)
        assert result["output"] == "Hello {{unknown}}"


class TestOutputModule:
    @pytest.mark.asyncio
    async def test_output_text_format(self):
        mod = OutputModule()
        ctx = ExecutionContext()
        result = await mod.execute({"format": "text"}, {"input": "hello"}, ctx)
        assert result == {"output": "hello"}

    @pytest.mark.asyncio
    async def test_output_json_format(self):
        mod = OutputModule()
        ctx = ExecutionContext()
        result = await mod.execute({"format": "json"}, {"input": '{"key": "value"}'}, ctx)
        assert result == {"output": {"key": "value"}}

    @pytest.mark.asyncio
    async def test_output_json_format_invalid_json(self):
        mod = OutputModule()
        ctx = ExecutionContext()
        result = await mod.execute({"format": "json"}, {"input": "not json"}, ctx)
        assert result == {"output": "not json"}


class TestConditionalModule:
    @pytest.mark.asyncio
    async def test_contains_true(self):
        mod = ConditionalModule()
        ctx = ExecutionContext()
        result = await mod.execute(
            {"conditionType": "contains", "conditionValue": "hello"},
            {"input": "say hello world"},
            ctx,
        )
        assert result["branch"] == "true"
        assert result["condition_result"] is True

    @pytest.mark.asyncio
    async def test_contains_false(self):
        mod = ConditionalModule()
        ctx = ExecutionContext()
        result = await mod.execute(
            {"conditionType": "contains", "conditionValue": "goodbye"},
            {"input": "say hello world"},
            ctx,
        )
        assert result["branch"] == "false"

    @pytest.mark.asyncio
    async def test_equals(self):
        mod = ConditionalModule()
        ctx = ExecutionContext()
        result = await mod.execute(
            {"conditionType": "equals", "conditionValue": "hello"},
            {"input": "hello"},
            ctx,
        )
        assert result["branch"] == "true"

    @pytest.mark.asyncio
    async def test_not_equals(self):
        mod = ConditionalModule()
        ctx = ExecutionContext()
        result = await mod.execute(
            {"conditionType": "not_equals", "conditionValue": "hello"},
            {"input": "world"},
            ctx,
        )
        assert result["branch"] == "true"

    @pytest.mark.asyncio
    async def test_greater_than(self):
        mod = ConditionalModule()
        ctx = ExecutionContext()
        result = await mod.execute(
            {"conditionType": "greater_than", "conditionValue": "5"},
            {"input": "10"},
            ctx,
        )
        assert result["branch"] == "true"

    @pytest.mark.asyncio
    async def test_less_than(self):
        mod = ConditionalModule()
        ctx = ExecutionContext()
        result = await mod.execute(
            {"conditionType": "less_than", "conditionValue": "5"},
            {"input": "3"},
            ctx,
        )
        assert result["branch"] == "true"


class TestTransformModule:
    @pytest.mark.asyncio
    async def test_passthrough(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute({"transformation": "passthrough"}, {"input": "hello"}, ctx)
        assert result == {"output": "hello"}

    @pytest.mark.asyncio
    async def test_json_parse(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute({"transformation": "json_parse"}, {"input": '{"key": "value"}'}, ctx)
        assert result == {"output": {"key": "value"}}

    @pytest.mark.asyncio
    async def test_json_stringify(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute({"transformation": "json_stringify"}, {"input": {"key": "value"}}, ctx)
        assert '"key": "value"' in result["output"]

    @pytest.mark.asyncio
    async def test_uppercase(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute({"transformation": "uppercase"}, {"input": "hello"}, ctx)
        assert result == {"output": "HELLO"}

    @pytest.mark.asyncio
    async def test_lowercase(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute({"transformation": "lowercase"}, {"input": "HELLO"}, ctx)
        assert result == {"output": "hello"}

    @pytest.mark.asyncio
    async def test_trim(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute({"transformation": "trim"}, {"input": "  hello  "}, ctx)
        assert result == {"output": "hello"}

    @pytest.mark.asyncio
    async def test_split(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute({"transformation": "split", "delimiter": ","}, {"input": "a,b,c"}, ctx)
        assert result == {"output": ["a", "b", "c"]}

    @pytest.mark.asyncio
    async def test_join(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute({"transformation": "join", "delimiter": " "}, {"input": ["hello", "world"]}, ctx)
        assert result == {"output": "hello world"}

    @pytest.mark.asyncio
    async def test_extract_field_from_dict(self):
        mod = TransformModule()
        ctx = ExecutionContext()
        result = await mod.execute(
            {"transformation": "extract_field", "field": "name"},
            {"input": {"name": "Alice", "age": 30}},
            ctx,
        )
        assert result == {"output": "Alice"}


class TestHttpRequestModule:
    @pytest.mark.asyncio
    async def test_get_request(self):
        mod = HttpRequestModule()
        ctx = ExecutionContext()
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}

        with patch("app.engine.modules.http_request.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await mod.execute(
                {"method": "GET", "url": "https://api.example.com/data"},
                {},
                ctx,
            )
            assert result["status_code"] == 200
            assert result["output"] == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_url_substitution(self):
        mod = HttpRequestModule()
        ctx = ExecutionContext()

        with patch("app.engine.modules.http_request.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {}
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(return_value=mock_response)

            await mod.execute(
                {"method": "GET", "url": "https://api.example.com/{{input}}/data"},
                {"input": "users"},
                ctx,
            )
            call_args = mock_client.request.call_args
            assert call_args.kwargs["url"] == "https://api.example.com/users/data"


class TestAgentModule:
    @pytest.mark.asyncio
    async def test_unsupported_provider(self):
        mod = AgentModule()
        ctx = ExecutionContext()
        result = await mod.execute(
            {"provider": "unsupported"},
            {"input": "hello"},
            ctx,
        )
        assert "Unsupported provider" in result["response"]

    @pytest.mark.asyncio
    async def test_openai_call(self):
        mod = AgentModule()
        ctx = ExecutionContext()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="AI response"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        with patch("app.engine.modules.agent.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(OPENAI_API_KEY="test-key")
            with patch("openai.AsyncOpenAI") as mock_openai:
                mock_client = AsyncMock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                result = await mod.execute(
                    {"provider": "openai", "model": "gpt-4", "systemPrompt": "You are helpful"},
                    {"input": "hello"},
                    ctx,
                )
                assert result["output"] == "AI response"
                assert ctx.total_token_usage["prompt_tokens"] == 10

    @pytest.mark.asyncio
    async def test_anthropic_call(self):
        mod = AgentModule()
        ctx = ExecutionContext()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Claude response")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        with patch("app.engine.modules.agent.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ANTHROPIC_API_KEY="test-key")
            with patch("anthropic.AsyncAnthropic") as mock_anthropic:
                mock_client = AsyncMock()
                mock_client.messages.create = AsyncMock(return_value=mock_response)
                mock_anthropic.return_value = mock_client

                result = await mod.execute(
                    {"provider": "anthropic", "model": "claude-3", "systemPrompt": "You are helpful"},
                    {"input": "hello"},
                    ctx,
                )
                assert result["output"] == "Claude response"
                assert ctx.total_token_usage["prompt_tokens"] == 10
