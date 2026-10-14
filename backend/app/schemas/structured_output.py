from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FieldType = Literal["string", "number", "integer", "boolean", "any", "list", "reference"]
ItemType = Literal["string", "number", "integer", "boolean", "any", "reference"]
ScalarType = Literal["string", "number", "integer", "boolean", "any"]

FIELD_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"
DEFINITION_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_]*$"


class OutputField(BaseModel):
    """One entry in a definition's field list.

    Only the keys that are valid for `type` are ever set; the rest stay absent
    rather than being stored as null.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64, pattern=FIELD_NAME_PATTERN)
    type: FieldType
    description: str = Field(min_length=1)
    required: bool = True
    items_type: ItemType | None = None
    items_ref: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=DEFINITION_NAME_PATTERN
    )
    ref: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=DEFINITION_NAME_PATTERN
    )

    @model_validator(mode="after")
    def _check_keys_match_type(self) -> "OutputField":
        if self.type == "list":
            if self.items_type is None:
                raise ValueError("a list field must declare what its items are")
            if self.items_type == "reference" and not self.items_ref:
                raise ValueError("a list of references must name the definition it references")
            if self.items_type != "reference" and self.items_ref:
                raise ValueError("items_ref is only valid when the items are references")
        elif self.items_type or self.items_ref:
            raise ValueError("items_type and items_ref are only valid on a list field")

        if self.type == "reference" and not self.ref:
            raise ValueError("a reference field must name the definition it references")
        if self.type != "reference" and self.ref:
            raise ValueError("ref is only valid on a reference field")
        return self

    def to_storage(self) -> dict[str, Any]:
        """The stored JSON for this field, with type-invalid keys left out."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> "OutputField":
        return cls.model_validate(data)


class StructuredOutputCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=DEFINITION_NAME_PATTERN)
    description: str = Field(min_length=1)
    fields: list[OutputField] = Field(min_length=1)


class StructuredOutputUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=DEFINITION_NAME_PATTERN)
    description: str = Field(min_length=1)
    fields: list[OutputField] = Field(min_length=1)


class StructuredOutputResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    fields: list[OutputField]
    referenced_by: list[str] = Field(default_factory=list)
    compiled_schema: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class StructuredOutputListResponse(BaseModel):
    structured_outputs: list[StructuredOutputResponse]
    total: int


class ParseSchemaRequest(BaseModel):
    # `schema` is aliased because the plain name shadows a BaseModel method.
    model_config = ConfigDict(populate_by_name=True)

    raw_schema: str = Field(alias="schema", min_length=1)


class ParseSchemaResponse(BaseModel):
    fields: list[OutputField]
    title: str | None = None
    description: str | None = None
