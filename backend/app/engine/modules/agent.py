from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext
from app.config import get_settings


class AgentModule(BaseModule):
    """LLM agent module - makes calls to AI providers."""

    module_type = "agent"

    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        provider = config.get("provider", "openai")
        model = config.get("model", "gpt-3.5-turbo")
        system_prompt = config.get("systemPrompt", "You are a helpful assistant.")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("maxTokens", 1000)

        # Get the input text from upstream nodes
        input_text = inputs.get("input", "")
        if isinstance(input_text, dict):
            input_text = str(input_text)

        settings = get_settings()

        if provider == "openai":
            return await self._call_openai(
                model, system_prompt, input_text, temperature, max_tokens, settings, context
            )
        elif provider == "anthropic":
            return await self._call_anthropic(
                model, system_prompt, input_text, temperature, max_tokens, settings, context
            )
        else:
            return {"response": f"[Unsupported provider: {provider}]", "token_usage": {}}

    async def _call_openai(
        self, model, system_prompt, input_text, temperature, max_tokens, settings, context
    ) -> dict[str, Any]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
        context.add_token_usage(usage)

        return {
            "response": response.choices[0].message.content,
            "output": response.choices[0].message.content,
            "token_usage": usage,
        }

    async def _call_anthropic(
        self, model, system_prompt, input_text, temperature, max_tokens, settings, context
    ) -> dict[str, Any]:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=model or "claude-3-haiku-20240307",
            system=system_prompt,
            messages=[{"role": "user", "content": input_text}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }
        context.add_token_usage(usage)

        return {
            "response": response.content[0].text,
            "output": response.content[0].text,
            "token_usage": usage,
        }
