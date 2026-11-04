"""The SQL guard — D3, layer 3 (spec §1 D3, §2.2).

Pure parsing and allowlist checks, no I/O and no async. A statement passes only
if it is a single SELECT-family query that touches nothing outside the caller's
table selection. `run()` refuses to execute whatever this refuses, and the
executor's use of the extended protocol is the structural backstop behind it.

Known shortcut (spec §2.8): identifier comparison is case-insensitive, so
"Foo" and "foo" are conflated. Upgrade to catalog OIDs if that ever matters.
"""

import re
from typing import Any

import sqlglot
from sqlglot import exp

MAX_SQL_BYTES = 100_000

# SELECT-family roots only. WITH parses as a Select carrying a With clause, so
# CTE queries pass through here; EXPLAIN/SHOW/DO/VACUUM arrive as exp.Command,
# COPY as exp.Copy — everything not in this tuple is rejected by type alone.
_ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)

# Per-dialect refusals. System schemas are refused unless the caller selected
# them explicitly (they are reachable-by-default in every other MCP-style
# server; here they are not). Function denylists are a floor, not an
# exhaustive list — the root causes (file reads, cross-database reach,
# server-state mutation, denial of service) are what each name stands for.
_POSTGRES_SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")
_MYSQL_SYSTEM_SCHEMAS = ("information_schema", "mysql", "performance_schema", "sys")

_POSTGRES_DANGEROUS_FUNCTIONS = (
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "lo_import",
    "lo_export",
    "dblink",
    "set_config",
    "pg_terminate_backend",
    "pg_cancel_backend",
)
_MYSQL_DANGEROUS_FUNCTIONS = (
    "load_file",
    "sleep",
    "benchmark",
    "sys_exec",
    "sys_eval",
)

_SYSTEM_SCHEMAS_BY_DIALECT = {
    "postgres": _POSTGRES_SYSTEM_SCHEMAS,
    "mysql": _MYSQL_SYSTEM_SCHEMAS,
}
_DANGEROUS_FUNCTIONS_BY_DIALECT = {
    "postgres": _POSTGRES_DANGEROUS_FUNCTIONS,
    "mysql": _MYSQL_DANGEROUS_FUNCTIONS,
}

_PLACEHOLDER_RE = re.compile(r"\$\d+\b")


class GuardError(Exception):
    """The statement was refused. `reason` is safe to show to the model."""

    def __init__(self, reason: str, sql: str):
        self.reason = reason
        self.sql = sql
        super().__init__(reason)


def validate(sql: str, dialect: str, allowed_tables: list[str]) -> exp.Expression:
    """Return the parsed statement, or raise GuardError naming the reason."""
    system_schemas = _SYSTEM_SCHEMAS_BY_DIALECT.get(dialect)
    dangerous_functions = _DANGEROUS_FUNCTIONS_BY_DIALECT.get(dialect)
    if system_schemas is None or dangerous_functions is None:
        raise GuardError(f"the dialect {dialect!r} is not supported", sql)
    if not sql or not sql.strip():
        raise GuardError("the query is empty", sql)
    if len(sql.encode("utf-8")) > MAX_SQL_BYTES:
        raise GuardError("the query exceeds the 100 KB limit", sql)
    if _PLACEHOLDER_RE.search(sql):
        raise GuardError("parameter placeholders are not supported", sql)

    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except sqlglot.errors.ParseError as e:
        raise GuardError(f"the query could not be parsed: {e}", sql) from e

    if len(statements) != 1:
        raise GuardError("exactly one SELECT statement is allowed", sql)
    expression = statements[0]

    if not isinstance(expression, _ALLOWED_ROOTS):
        raise GuardError("only SELECT queries are allowed", sql)
    if expression.args.get("into"):
        raise GuardError("SELECT ... INTO is not allowed", sql)
    if expression.args.get("locks"):
        raise GuardError("row locks (FOR UPDATE / FOR SHARE) are not allowed", sql)
    if expression.find(exp.Placeholder):
        raise GuardError("parameter placeholders are not supported", sql)

    cte_names = _cte_names(expression)
    allowed = _parse_allowed(allowed_tables)

    for func in expression.find_all(exp.Func):
        for name in _function_names(func):
            if name in dangerous_functions:
                raise GuardError(f"the function {name}() is not allowed", sql)

    for table in expression.find_all(exp.Table):
        name = table.name
        if name in cte_names:
            continue
        _check_table(table, allowed, sql, system_schemas)

    return expression


def _function_names(func: exp.Func) -> list[str]:
    """All plausible names of a function node, lowercased and unquoted."""
    names: list[str] = []
    sql_name = func.sql_name()
    if sql_name and sql_name != "ANONYMOUS":
        names.append(sql_name.lower().strip('"'))
    inner = func.this
    if isinstance(inner, (exp.Var, exp.Identifier)):
        names.append(inner.name.lower().strip('"'))
    elif isinstance(inner, str):
        names.append(inner.lower().strip('"'))
    return names


def _cte_names(expression: exp.Expression) -> set[str]:
    """CTE aliases visible in the statement; they are names, never tables."""
    return {
        cte.alias_or_name.lower()
        for with_node in expression.find_all(exp.With)
        for cte in with_node.find_all(exp.CTE)
    }


def _parse_allowed(allowed_tables: list[str]) -> set[tuple[str | None, str]]:
    """Entries are 'schema.table' or 'table'; lowercased for the case shortcut."""
    parsed: set[tuple[str | None, str]] = set()
    for entry in allowed_tables:
        parts = entry.split(".")
        if len(parts) == 2:
            parsed.add((parts[0].lower(), parts[1].lower()))
        elif len(parts) == 1:
            parsed.add((None, parts[0].lower()))
    return parsed


def _check_table(
    table: exp.Table,
    allowed: set[tuple[str | None, str]],
    sql: str,
    system_schemas: tuple[str, ...],
) -> None:
    name = table.name
    schema = table.db or None

    if schema and schema.lower() in system_schemas:
        if (schema.lower(), name.lower()) not in allowed:
            raise GuardError(f"the system table {schema}.{name} is not allowed", sql)
        return

    if schema is not None:
        matched = (schema.lower(), name.lower()) in allowed
    else:
        # An unqualified name matches any selected table with that name (spec §2.8).
        matched = (None, name.lower()) in allowed or any(
            n == name.lower() for _, n in allowed
        )

    if not matched:
        display = f"{schema}.{name}" if schema else name
        raise GuardError(f"the table {display} is not part of this agent's data sources", sql)
