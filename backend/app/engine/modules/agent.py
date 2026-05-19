from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext
from app.config import get_settings

_openai_clients = {}
_anthropic_clients = {}

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
        model = config.get("model")
        system_prompt = config.get("systemPrompt", "You are a helpful assistant.")
        temperature = config.get("temperature", 0.1)
        max_tokens = config.get("maxTokens", 1000)

        # Get the input text from upstream nodes
        input_text = inputs.get("input", "")
        if isinstance(input_text, dict):
            input_text = str(input_text)

        settings = get_settings()

        if provider == "openai":
            return await self._call_openai(
                model or "gpt-4o-mini", system_prompt, input_text, temperature, max_tokens, settings, context
            )
        elif provider == "anthropic":
            return await self._call_anthropic(
                model or "claude-3-5-haiku-20241022", system_prompt, input_text, temperature, max_tokens, settings, context
            )
        elif provider == "google" or provider == "gemini":
            return await self._call_gemini(
                model or "gemini-2.0-flash", system_prompt, input_text, temperature, max_tokens, settings, context
            )
        else:
            return {"response": f"[Unsupported provider: {provider}]", "token_usage": {}}

    async def _call_openai(
        self,
        model,
        system_prompt,
        input_text,
        temperature,
        max_tokens,
        settings,
        context
    ) -> dict[str, Any]:
        from openai import AsyncOpenAI
        
        api_key = settings.OPENAI_API_KEY
        if api_key not in _openai_clients:
            _openai_clients[api_key] = AsyncOpenAI(api_key=api_key)
        client = _openai_clients[api_key]
        
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
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        context.add_token_usage(usage)

        return {
            "response": response.choices[0].message.content,
            "output": response.choices[0].message.content,
            "token_usage": usage,
        }

    async def _call_anthropic(
        self,
        model,
        system_prompt,
        input_text,
        temperature,
        max_tokens,
        settings,
        context
    ) -> dict[str, Any]:
        from anthropic import AsyncAnthropic

        api_key = settings.ANTHROPIC_API_KEY
        if api_key not in _anthropic_clients:
            _anthropic_clients[api_key] = AsyncAnthropic(api_key=api_key)
        client = _anthropic_clients[api_key]
        
        response = await client.messages.create(
            model=model,
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

        # Extract text content from response blocks (filter out non-text blocks)
        text_content = ""
        for block in response.content:
            if hasattr(block, "text"):
                text_content += block.text

        return {
            "response": text_content,
            "output": text_content,
            "token_usage": usage,
        }



    async def _call_gemini(self,
                        model, 
                        system_prompt, 
                        input_text, 
                        temperature, 
                        max_tokens, 
                        settings, 
                        context
                        )-> dict[str, Any]:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        generative_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt
        )
        
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )
        
        response = await generative_model.generate_content_async(
            input_text,
            generation_config=generation_config
        )
        
        metadata = response.usage_metadata or {}
        usage = {
            "prompt_tokens": getattr(metadata, "prompt_token_count", 0) or 0,
            "completion_tokens": getattr(metadata, "candidates_token_count", 0) or 0,
            "total_tokens": getattr(metadata, "total_token_count", 0) or 0,
        }
        
        context.add_token_usage(usage)
        
        try:
            text_content = response.text
        except (ValueError, AttributeError):
            parts = []
            for candidate in (response.candidates or []):
                for part in (candidate.content.parts if candidate.content else []):
                    if hasattr(part, "text"):
                        parts.append(part.text)
            text_content = "".join(parts) or "[Response blocked by safety filters]"
        
        return {
            "response": text_content,
            "output": text_content,
            "token_usage": usage,
        }
