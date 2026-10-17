"""Request and response models for the Tools section.

`ToolParameter` and `ToolSchema` are what the extraction module produces and what
an LLM tool list consumes. The rest are the HTTP contract.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ParameterType = Literal[
    "string", "integer", "number", "boolean", "array", "object", "null", "any"
]
ItemType = Literal["string", "integer", "number", "boolean", "object", "any"]

TOOL_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


class ToolParameter(BaseModel):
    """One parameter of a tool.

    `items_type` is set only on an array parameter, so a scalar never carries a key
    that means nothing for it — the rule `OutputField` follows.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64, pattern=TOOL_NAME_PATTERN)
    type: ParameterType
    description: str = Field(min_length=1)
    required: bool = True
    items_type: ItemType | None = None

    @model_validator(mode="after")
    def _items_are_only_for_arrays(self) -> "ToolParameter":
        if self.type != "array" and self.items_type is not None:
            raise ValueError("items_type is only valid on an array parameter")
        return self


class ToolSchema(BaseModel):
    """A tool as the model will see it: a name, a description and its parameters."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64, pattern=TOOL_NAME_PATTERN)
    description: str = Field(min_length=1)
    parameters: list[ToolParameter] = Field(default_factory=list)
    returns: ParameterType = "any"


class ToolSchemaResponse(ToolSchema):
    """A schema plus the JSON Schema compiled from it."""

    input_schema: dict[str, Any]


class ToolResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    code: str
    parameters: list[ToolParameter]
    returns: ParameterType
    input_schema: dict[str, Any] | None = None
    category: Literal["custom"] = "custom"
    needs_sandbox: Literal[True] = True
    created_at: datetime
    updated_at: datetime


class ToolListResponse(BaseModel):
    tools: list[ToolResponse]
    total: int


class BuiltinToolResponse(BaseModel):
    """A built-in tool. ADR-015: name and description only — never the source."""

    built_in_key: str
    name: str
    description: str
    category: Literal["built-in"] = "built-in"
    needs_sandbox: Literal[False] = False


class BuiltinToolListResponse(BaseModel):
    tools: list[BuiltinToolResponse]
    total: int


class ToolWriteRequest(BaseModel):
    """The only thing a write carries is the code: name and schema come from it."""

    code: str = Field(min_length=1)


class ToolValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    schema: ToolSchemaResponse | None = None
