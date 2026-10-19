"""External and provider-native web search.

Tavily and Exa are ordinary LangChain tools. A provider's own search is a
built-in tool spec passed straight to `create_agent`, which forwards dict tools
to the model's `bind_tools`.
"""

from langchain_core.tools import BaseTool

_NATIVE_SPECS: dict[str, dict] = {
    "openai": {"type": "web_search"},
    "anthropic": {"type": "web_search_20250305", "name": "web_search", "max_uses": 5},
    "gemini": {"google_search": {}},
}


def build_web_search_tool(method: str, api_key: str) -> BaseTool | None:
    if method == "tavily":
        from langchain_tavily import TavilySearch

        return TavilySearch(tavily_api_key=api_key, max_results=5)

    if method == "exa":
        from langchain_exa import ExaSearchResults

        return ExaSearchResults(exa_api_key=api_key)

    return None


def native_web_search_spec(provider: str) -> dict | None:
    spec = _NATIVE_SPECS.get(provider)
    return dict(spec) if spec else None
