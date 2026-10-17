"""Token counting using tiktoken. Computed on read, never stored."""

import tiktoken


_ENCODING = tiktoken.get_encoding("o200k_base")


def count_tokens(text: str) -> int:
    """Return the token count for a text string. Uses o200k_base (GPT-4o family)."""
    return len(_ENCODING.encode(text))
