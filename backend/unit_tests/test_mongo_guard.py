"""The Mongo find guard (addendum 2026-11-05): pure, adversarial, no I/O.

Mongo has no SQL to parse; the boundary here is the allowlist plus the
code-execution operators. The tests are written as an attack surface.
"""

import pytest

from app.services.data_sources.mongo_guard import GuardError, validate_find

COLLECTIONS = ["orders", "customers"]


def _ok(filter_json: str = "{}", collection: str = "orders", projection: str | None = None):
    filter_doc, projection_doc, _limit = validate_find(
        collection, filter_json, projection, COLLECTIONS
    )
    return filter_doc, projection_doc


def _rejected(filter_json: str = "{}", collection: str = "orders", projection: str | None = None, match: str | None = None):
    with pytest.raises(GuardError, match=match):
        validate_find(collection, filter_json, projection, COLLECTIONS)


class TestCollectionAllowlist:
    def test_selected_collection_accepted(self):
        filter_doc, _ = _ok()
        assert filter_doc == {}

    def test_unselected_collection_rejected(self):
        _rejected(collection="users", match="users")

    def test_collection_name_is_exact(self):
        # Mongo collection names are case-sensitive; the snapshot matches exactly.
        _rejected(collection="Orders")


class TestFilterDocument:
    def test_empty_filter_accepted(self):
        filter_doc, _ = _ok("{}")
        assert filter_doc == {}

    def test_plain_operators_accepted(self):
        filter_doc, _ = _ok('{"status": "paid", "total": {"$gt": 100}}')
        assert filter_doc["total"] == {"$gt": 100}

    def test_where_is_rejected(self):
        _rejected('{"$where": "this.total > 0"}', match=r"\$where")

    def test_function_is_rejected(self):
        _rejected('{"$expr": {"$function": {"body": "return true", "args": [], "lang": "js"}}}', match=r"\$function")

    def test_accumulator_is_rejected(self):
        _rejected('{"$expr": {"$accumulator": {"init": "return 1"}}}', match=r"\$accumulator")

    def test_nested_where_is_rejected(self):
        _rejected('{"items": {"$elemMatch": {"$where": "true"}}}', match=r"\$where")

    def test_non_object_filter_rejected(self):
        _rejected('[1, 2, 3]', match="object")

    def test_malformed_json_rejected(self):
        _rejected('{"total": }', match="parse")

    def test_oversized_filter_rejected(self):
        _rejected('{"note": "' + "x" * 17_000 + '"}', match="16 KB")


class TestProjection:
    def test_plain_projection_accepted(self):
        _, projection = _ok(projection='{"total": 1}')
        assert projection == {"total": 1}

    def test_dollar_projection_rejected(self):
        _rejected(projection='{"total": {"$slice": 5}}', match="projection")


class TestLimit:
    def test_default_limit_is_two_hundred(self):
        filter_doc, projection, limit = validate_find("orders", "{}", None, COLLECTIONS)
        assert limit == 200

    def test_limit_capped_at_two_hundred(self):
        _, _, limit = validate_find("orders", "{}", None, COLLECTIONS, limit=5_000)
        assert limit == 200

    def test_limit_must_be_positive(self):
        with pytest.raises(GuardError, match="limit"):
            validate_find("orders", "{}", None, COLLECTIONS, limit=0)
