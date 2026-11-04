"""The Mongo find guard (addendum 2026-11-05) — D3 layer 3 for MongoDB.

Pure parsing and allowlist checks, no I/O and no async. Mongo has no SQL to
parse, so the boundary is: the collection must be in the caller's snapshot,
the filter/projection must be JSON objects, and the operators that execute
code are refused outright. `find` only — no aggregations, no writes.
"""

import json

MAX_FILTER_BYTES = 16_000
DEFAULT_LIMIT = 200
MAX_LIMIT = 200

# Operators that run server-side JavaScript or otherwise execute arbitrary
# expressions. Everything else ($gt, $elemMatch, $regex, ...) is data-shaped
# and allowed — Mongo operators are $-prefixed by nature, so "$" alone is not
# the boundary; these three are.
_DENIED_OPERATORS = ("$where", "$function", "$accumulator")


class GuardError(Exception):
    """The find was refused. `reason` is safe to show to the model."""


def _walk_keys(document: dict, path: str) -> None:
    for key, value in document.items():
        if not isinstance(key, str):
            raise GuardError(f"{path} keys must be strings")
        lowered = key.lower()
        for denied in _DENIED_OPERATORS:
            if lowered == denied:
                raise GuardError(f"the operator {denied} is not allowed")
        if isinstance(value, dict):
            _walk_keys(value, path)


def _has_dollar_key(document: dict) -> bool:
    for key, value in document.items():
        if isinstance(key, str) and key.startswith("$"):
            return True
        if isinstance(value, dict) and _has_dollar_key(value):
            return True
    return False


def validate_find(
    collection: str,
    filter_json: str,
    projection_json: str | None,
    allowed_collections: list[str],
    limit: int | None = None,
) -> tuple[dict, dict | None, int]:
    """Return (filter_doc, projection_doc, limit), or raise GuardError."""
    if collection not in allowed_collections:
        raise GuardError(
            f"the collection {collection!r} is not part of this agent's data sources"
        )

    if len(filter_json.encode("utf-8")) > MAX_FILTER_BYTES:
        raise GuardError("the filter exceeds the 16 KB limit")
    try:
        filter_doc = json.loads(filter_json)
    except json.JSONDecodeError as e:
        raise GuardError(f"the filter could not be parsed as JSON: {e}") from e
    if not isinstance(filter_doc, dict):
        raise GuardError("the filter must be a JSON object")
    _walk_keys(filter_doc, "filter")

    projection_doc: dict | None = None
    if projection_json is not None:
        try:
            projection_doc = json.loads(projection_json)
        except json.JSONDecodeError as e:
            raise GuardError(f"the projection could not be parsed as JSON: {e}") from e
        if not isinstance(projection_doc, dict):
            raise GuardError("the projection must be a JSON object")
        # v1 projections are plain field inclusion/exclusion only — no $ keys
        # at any depth (a $slice or $meta here is convenience, not necessity).
        if _has_dollar_key(projection_doc):
            raise GuardError("projection operators are not allowed; use plain field names")

    if limit is None:
        limit = DEFAULT_LIMIT
    if not isinstance(limit, int) or limit < 1:
        raise GuardError("the limit must be a positive integer")
    return filter_doc, projection_doc, min(limit, MAX_LIMIT)
