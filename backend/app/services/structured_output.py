"""Compile structured output definitions into JSON Schema, and parse JSON
Schema back into fields.

Pure module: it never touches the database and no ORM object crosses into it.
Callers reduce their rows to `Definition` objects, which is also what tests
build directly.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from app.schemas.structured_output import OutputField


class StructuredOutputError(Exception):
    """A definition cannot compile, or pasted JSON Schema cannot be converted."""


@dataclass(frozen=True)
class Definition:
    """A structured output, reduced to what compilation needs."""

    name: str
    description: str
    fields: list[OutputField]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", [OutputField.model_validate(f) for f in self.fields])


@dataclass(frozen=True)
class ParsedSchema:
    fields: list[OutputField]
    title: str | None
    description: str | None


SCALAR_TYPES = frozenset({"string", "number", "integer", "boolean", "any"})
LIST_ITEM_TYPES = SCALAR_TYPES | {"reference"}

_SCALAR_FIELD_TYPES = SCALAR_TYPES | {"list", "reference"}

_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REF_PREFIX = "#/$defs/"


# --------------------------------------------------------------------------- #
# Compilation
# --------------------------------------------------------------------------- #


def compile_schema(definition: Definition, workspace_defs: dict[str, Definition]) -> dict[str, Any]:
    """Compile one definition into JSON Schema.

    `workspace_defs` is every definition in the workspace, keyed by name, so
    references can be resolved and the transitive closure collected. Raises
    `StructuredOutputError` for an unknown reference or a reference cycle.
    """
    _validate_definition(definition)
    collected = _collect_defs(definition, workspace_defs)

    return {
        "title": definition.name,
        "description": definition.description,
        "type": "object",
        "properties": {field.name: _compile_field(field) for field in definition.fields},
        "required": [field.name for field in definition.fields if field.required],
        "additionalProperties": False,
        "$defs": {name: _compile_object(target) for name, target in collected.items()},
    }


def find_referrers(name: str, workspace_defs: dict[str, Definition]) -> list[str]:
    """Names of every definition that references `name`."""
    wanted = name.lower()
    return sorted(
        other.name
        for other in workspace_defs.values()
        if any(target.lower() == wanted for target in _referenced_names(other))
    )


def _validate_definition(definition: Definition) -> None:
    if not definition.fields:
        raise StructuredOutputError(f"'{definition.name}' has no fields.")

    seen: set[str] = set()
    for field in definition.fields:
        if field.type not in _SCALAR_FIELD_TYPES:
            raise StructuredOutputError(f"'{field.name}' has an unsupported type '{field.type}'.")
        if field.type == "list" and field.items_type not in LIST_ITEM_TYPES:
            raise StructuredOutputError(f"'{field.name}' has an unsupported item type.")

        key = field.name.lower()
        if key in seen:
            raise StructuredOutputError(
                f"'{definition.name}' has two fields named '{field.name}'. "
                "Field names must be unique, ignoring case."
            )
        seen.add(key)


def _compile_field(field: OutputField) -> dict[str, Any]:
    if field.type == "reference":
        return {"$ref": f"{_REF_PREFIX}{field.ref}", "description": field.description}

    if field.type == "list":
        if field.items_type == "reference":
            items: dict[str, Any] = {"$ref": f"{_REF_PREFIX}{field.items_ref}"}
        elif field.items_type == "any":
            items = {}
        else:
            items = {"type": field.items_type}
        return {"type": "array", "description": field.description, "items": items}

    if field.type == "any":
        # No `type` key at all — that is what makes the field unconstrained.
        return {"description": field.description}

    return {"type": field.type, "description": field.description}


def _compile_object(definition: Definition) -> dict[str, Any]:
    return {
        "title": definition.name,
        "description": definition.description,
        "type": "object",
        "properties": {field.name: _compile_field(field) for field in definition.fields},
        "required": [field.name for field in definition.fields if field.required],
        "additionalProperties": False,
    }


def _referenced_names(definition: Definition) -> list[str]:
    names: list[str] = []
    for field in definition.fields:
        if field.type == "reference" and field.ref:
            names.append(field.ref)
        elif field.type == "list" and field.items_type == "reference" and field.items_ref:
            names.append(field.items_ref)
    return names


def _lookup(name: str, workspace_defs: dict[str, Definition]) -> Definition:
    wanted = name.lower()
    for key, definition in workspace_defs.items():
        if key.lower() == wanted:
            return definition
    raise StructuredOutputError(
        f"'{name}' is not a structured output in this workspace, so it cannot be referenced."
    )


def _collect_defs(root: Definition, workspace_defs: dict[str, Definition]) -> dict[str, Definition]:
    """Walk forward from the root, collecting the transitive closure.

    Reaching a definition that is already on the current path is a cycle, and
    the error names the path so the user can see the loop they built.
    """
    collected: dict[str, Definition] = {}

    def walk(definition: Definition, path: list[str]) -> None:
        for target_name in _referenced_names(definition):
            target = _lookup(target_name, workspace_defs)
            if target.name in path:
                raise StructuredOutputError(
                    "Circular reference: " + " → ".join([*path, target.name])
                )
            if target.name in collected:
                continue
            collected[target.name] = target
            walk(target, [*path, target.name])

    walk(root, [root.name])
    # The root describes itself; it has no business inside its own $defs.
    collected.pop(root.name, None)
    return collected


# --------------------------------------------------------------------------- #
# Paste parsing
# --------------------------------------------------------------------------- #

_ALLOWED_ROOT_KEYS = {
    "type",
    "title",
    "description",
    "properties",
    "required",
    "additionalProperties",
    "$schema",
}
_ALLOWED_PROPERTY_KEYS = {"type", "description", "items", "$ref", "title", "additionalProperties"}
_ALLOWED_ITEM_KEYS = {"type", "description", "title"}


def parse_json_schema(raw: str, existing_names: Iterable[str]) -> ParsedSchema:
    """Convert pasted JSON Schema into fields.

    A converter, not a second store: callers save the returned fields and
    compile the schema back out. `existing_names` are the definitions already
    saved in the workspace, which is what `$ref`s resolve against.
    """
    saved = set(existing_names)

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise StructuredOutputError(f"That is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise StructuredOutputError("The schema must be a JSON object.")

    _reject_local_defs(data)
    _reject_unknown_keys(data, _ALLOWED_ROOT_KEYS, "the schema root")

    if data.get("type") != "object":
        raise StructuredOutputError('The schema root must be an object: add "type": "object".')

    properties = data.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise StructuredOutputError('The schema must declare at least one property under "properties".')

    required = data.get("required", [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise StructuredOutputError('"required" must be a list of property names.')
    for name in required:
        if name not in properties:
            raise StructuredOutputError(
                f'"required" lists {name}, which is not one of the properties.'
            )

    fields: list[OutputField] = []
    seen: set[str] = set()
    for name, spec in properties.items():
        field = _parse_property(name, spec, required, saved)
        if field.name.lower() in seen:
            raise StructuredOutputError(
                f'"{field.name}" appears twice. Field names must be unique, ignoring case.'
            )
        seen.add(field.name.lower())
        fields.append(field)

    title = data.get("title") if isinstance(data.get("title"), str) else None
    description = data.get("description") if isinstance(data.get("description"), str) else None
    return ParsedSchema(fields=fields, title=title, description=description)


def _reject_local_defs(data: dict[str, Any]) -> None:
    for keyword in ("$defs", "definitions"):
        if keyword in data:
            raise StructuredOutputError(
                f"This schema carries its own {keyword} block. Paste one definition at a time: "
                "save the referenced outputs first, then point at them by name."
            )


def _reject_unknown_keys(spec: dict[str, Any], allowed: set[str], where: str) -> None:
    for key in spec:
        if key not in allowed:
            raise StructuredOutputError(
                f'"{key}" is not supported in {where}. Supported keys are: '
                + ", ".join(sorted(allowed))
                + "."
            )


def _parse_property(
    name: str, spec: Any, required: list[str], saved: set[str]
) -> OutputField:
    if not _FIELD_NAME_RE.match(name) or len(name) > 64:
        raise StructuredOutputError(
            f'"{name}" is not a usable field name. Use letters, digits and underscores, '
            "starting with a letter or underscore."
        )
    if not isinstance(spec, dict):
        raise StructuredOutputError(f'The schema for "{name}" must be an object.')

    if "properties" in spec:
        raise StructuredOutputError(
            f'"{name}" is an inline nested object. Save that shape as its own structured '
            "output and reference it by name instead."
        )

    _reject_unknown_keys(spec, _ALLOWED_PROPERTY_KEYS, f'"{name}"')

    description = spec.get("description")
    if not isinstance(description, str) or not description.strip():
        raise StructuredOutputError(
            f'"{name}" needs a description. It is the instruction the model gets for that field.'
        )

    common = {
        "name": name,
        "description": description,
        "required": name in required,
    }

    if "$ref" in spec:
        return OutputField(
            **common, type="reference", ref=_resolve_ref(spec["$ref"], name, saved)
        )

    declared = spec.get("type")

    if declared == "object":
        raise StructuredOutputError(
            f'"{name}" is an inline nested object. Save that shape as its own structured '
            "output and reference it by name instead."
        )

    if declared == "array":
        return _parse_array(common, spec, name, saved)

    if declared is None:
        return OutputField(**common, type="any")

    if declared not in SCALAR_TYPES:
        raise StructuredOutputError(f'"{name}" has an unsupported type "{declared}".')

    return OutputField(**common, type=declared)


def _parse_array(
    common: dict[str, Any], spec: dict[str, Any], name: str, saved: set[str]
) -> OutputField:
    items = spec.get("items")
    if items is None:
        raise StructuredOutputError(f'"{name}" is an array but does not declare what its items are.')
    if isinstance(items, list):
        raise StructuredOutputError(
            f'"{name}" is a tuple array (its "items" is a list), which is not supported.'
        )
    if not isinstance(items, dict):
        raise StructuredOutputError(f'The "items" of "{name}" must be an object.')

    if "$ref" in items:
        return OutputField(
            **common,
            type="list",
            items_type="reference",
            items_ref=_resolve_ref(items["$ref"], name, saved),
        )

    item_type = items.get("type")
    if item_type == "object":
        raise StructuredOutputError(
            f'"{name}" is a list of inline objects. Save that shape as its own structured '
            "output and reference it, so it is defined once."
        )
    if item_type == "array":
        raise StructuredOutputError(f'"{name}" is a list of lists, which is not supported.')
    if item_type is not None and item_type not in SCALAR_TYPES:
        raise StructuredOutputError(f'"{name}" has an unsupported item type "{item_type}".')

    _reject_unknown_keys(items, _ALLOWED_ITEM_KEYS, f'"{name}".items')

    return OutputField(**common, type="list", items_type=item_type or "any")


def _resolve_ref(ref: Any, field_name: str, saved: set[str]) -> str:
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        raise StructuredOutputError(
            f'"{field_name}" points at "{ref}", which is not a saved structured output. '
            f'References look like "{_REF_PREFIX}Name".'
        )

    target = ref[len(_REF_PREFIX) :]
    wanted = target.lower()
    for name in saved:
        if name.lower() == wanted:
            return name

    raise StructuredOutputError(
        f'"{field_name}" references "{target}", which is not a saved structured output '
        "in this workspace. Save it first, then reference it."
    )
