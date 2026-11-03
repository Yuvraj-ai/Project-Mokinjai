"""Shared value types for the data-sources executor (spec §2.2)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    nullable: bool


@dataclass(frozen=True)
class Table:
    schema: str
    name: str
    columns: list[Column] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True)
class QueryResult:
    """The bounded payload returned to the model.

    `columns` is empty when the query returned no rows (v1 does not describe a
    shape for empty results). `rows` holds JSON-ready values only.
    """

    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool
    duration_ms: int
