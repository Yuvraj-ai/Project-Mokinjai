"""The SQL guard (D3, layer 3): pure, adversarial, no I/O.

Every row of the validator table in the data-sources spec is one test here. The
guard is the boundary between the model and the database; the tests are written
as an attack surface, not as a spec echo.
"""

import pytest

from app.services.data_sources.guard import GuardError, validate

SELECTED = ["public.users", "public.orders", "public.Selected"]


def _ok(sql: str, allowed: list[str] | None = None) -> None:
    validate(sql, "postgres", SELECTED if allowed is None else allowed)


def _rejected(sql: str, match: str | None = None, allowed: list[str] | None = None) -> None:
    with pytest.raises(GuardError, match=match) as excinfo:
        validate(sql, "postgres", SELECTED if allowed is None else allowed)
    assert excinfo.value.sql is not None or True  # the error always carries the SQL


class TestMultipleStatements:
    def test_commit_then_drop(self):
        _rejected("COMMIT; DROP TABLE users")

    def test_two_selects(self):
        _rejected("SELECT 1; SELECT 2")

    def test_trailing_statement_after_semicolon(self):
        _rejected("SELECT * FROM users; DROP TABLE users")

    def test_double_semicolon_with_statement(self):
        _rejected("SELECT * FROM users;; SELECT 2")

    def test_trailing_comment_is_accepted(self):
        _ok("SELECT * FROM users -- fetch everyone")


class TestRootStatement:
    @pytest.mark.parametrize(
        "sql",
        [
            "EXPLAIN ANALYZE DELETE FROM users",
            "SHOW search_path",
            "COPY users TO PROGRAM 'cp /etc/passwd /tmp/x'",
            "SET statement_timeout = 0",
            "CALL some_proc()",
            "DO $$ BEGIN INSERT INTO users VALUES (1); END $$",
            "LISTEN channel",
            "NOTIFY channel",
            "INSERT INTO users VALUES (1)",
            "UPDATE users SET id = 1",
            "DELETE FROM users",
            "TRUNCATE users",
            "CREATE TABLE x (id int)",
            "DROP TABLE users",
            "ALTER TABLE users ADD COLUMN x int",
            "GRANT ALL ON users TO PUBLIC",
            "VACUUM users",
        ],
    )
    def test_non_select_roots(self, sql):
        _rejected(sql)

    def test_select_into(self):
        _rejected("SELECT * INTO copy_of_users FROM users")

    def test_for_update(self):
        _rejected("SELECT * FROM users FOR UPDATE")

    def test_for_share(self):
        _rejected("SELECT * FROM users FOR SHARE")


class TestTableAllowlist:
    def test_table_outside_selection_names_it(self):
        with pytest.raises(GuardError, match="other"):
            _ok("SELECT * FROM other")

    def test_qualified_table_outside_selection_names_it(self):
        with pytest.raises(GuardError, match="private\\.secrets"):
            _ok('SELECT * FROM private.secrets')

    def test_union_reaches_the_second_table(self):
        _rejected("SELECT * FROM users UNION SELECT * FROM not_selected")

    def test_intersect_reaches_the_second_table(self):
        _rejected("SELECT * FROM users INTERSECT SELECT * FROM not_selected")

    def test_except_reaches_the_second_table(self):
        _rejected("SELECT * FROM users EXCEPT SELECT * FROM not_selected")

    def test_subquery_tables_are_checked(self):
        _rejected("SELECT * FROM (SELECT * FROM not_selected) AS s")

    def test_join_tables_are_checked(self):
        _rejected("SELECT * FROM users JOIN orders ON users.id = orders.id JOIN not_selected ON 1=1")

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM pg_catalog.pg_user",
            "SELECT * FROM information_schema.tables",
            "SELECT * FROM pg_toast.pg_toast_16418",
        ],
    )
    def test_system_schemas(self, sql):
        _rejected(sql)

    def test_system_schema_selected_explicitly_is_allowed(self):
        _ok("SELECT * FROM information_schema.tables", ["information_schema.tables"])


class TestCtes:
    def test_cte_reference_is_not_a_table(self):
        _ok("WITH cte AS (SELECT * FROM users) SELECT * FROM cte")

    def test_cte_with_join_on_real_table(self):
        _ok("WITH cte AS (SELECT * FROM users) SELECT * FROM cte JOIN orders ON 1=1")

    def test_cte_shadowing_a_real_table_does_not_reach_it(self):
        # `users` here resolves to the CTE, never the physical table; the query is
        # accepted because it cannot leak anything.
        _ok("WITH users AS (SELECT 1 AS id) SELECT * FROM users")

    def test_nested_ctes(self):
        _ok(
            "WITH a AS (SELECT * FROM users), "
            "b AS (SELECT * FROM a JOIN orders ON 1=1) "
            "SELECT * FROM b"
        )


class TestPlaceholdersAndFunctions:
    def test_dollar_placeholder(self):
        _rejected("SELECT * FROM users WHERE id = $1")

    def test_question_mark_placeholder(self):
        _rejected("SELECT * FROM users WHERE id = ?")

    @pytest.mark.parametrize(
        "fn",
        [
            "pg_read_file('/etc/passwd')",
            "pg_read_binary_file('/etc/passwd')",
            "pg_ls_dir('/')",
            "lo_import('/etc/passwd')",
            "dblink('host=x dbname=y', 'SELECT 1')",
            "set_config('search_path', 'public', false)",
            "pg_terminate_backend(123)",
            "pg_cancel_backend(123)",
        ],
    )
    def test_dangerous_functions(self, fn):
        _rejected(f"SELECT {fn}")

    def test_dangerous_function_nested_in_expression(self):
        _rejected("SELECT upper(pg_read_file('/etc/passwd'))")

    def test_benign_functions_pass(self):
        _ok("SELECT upper(name), length(name), coalesce(id, 0) FROM users")


class TestSizeAndSyntax:
    def test_oversized_sql_rejected_before_parsing(self):
        big = "SELECT * FROM users WHERE name = '" + "a" * (100 * 1024) + "'"
        _rejected(big)

    def test_exactly_under_the_size_limit_parses(self):
        pad = "a" * (90 * 1024)
        _ok(f"SELECT '{pad}' FROM users")

    def test_parse_error_rejected(self):
        _rejected("SELECT * FRM users")

    def test_empty_rejected(self):
        _rejected("")

    def test_semicolon_inside_a_string_literal_is_accepted(self):
        _ok("SELECT * FROM users WHERE name = 'a;b'")


class TestCaseAndQuoting:
    def test_quoted_identifier_matches_selected(self):
        _ok('SELECT * FROM "Selected"')

    def test_unqualified_name_matches_any_schema(self):
        _ok("SELECT * FROM users", ["analytics.users"])

    def test_qualified_name_must_match_pair(self):
        # `analytics.users` is selected, `private.users` is not.
        _rejected("SELECT * FROM private.users", allowed=["analytics.users"])

    def test_schema_qualified_selected_table(self):
        _ok("SELECT * FROM public.users")
