"""Extract a tool schema from user-written Python source.

Pure module: a string goes in and a result comes out. It never touches the
database and no ORM object crosses into it, the way
`app/services/structured_output.py` compiles JSON Schema from plain `Definition`
objects.

Errors come back as data and are never raised — not even for a syntax error. One
function therefore serves the live preview, the save gate and the built-in
registry's import-time self-check without three different error models.

Checks are layered, and a layer returns before the next one runs: there is no
signature to inspect in code that does not parse, and no parameter list to check
against a missing `Args:` section.
"""

import ast
import re
from dataclasses import dataclass
from typing import Any, cast

from pydantic import ValidationError

from app.schemas.tool import ItemType, ParameterType, ToolParameter, ToolSchema


@dataclass(frozen=True)
class ExtractionResult:
    """A tool schema, or every reason the source is not one yet."""

    schema: ToolSchema | None
    errors: list[str]


MAX_NAME_LENGTH = 64

# A docstring section header. The summary stops here even when the author left no
# blank line before it.
_SECTION_RE = re.compile(
    r"^(Args|Arguments|Returns|Yields|Raises|Examples?|Note|Notes|Attributes|See Also)\s*:?\s*$",
    re.IGNORECASE,
)
_ARGS_HEADER_RE = re.compile(r"^(Args|Arguments)\s*:\s*$", re.IGNORECASE)
# `city: what it means` or `city (str): what it means`. A type written in
# parentheses is accepted and ignored: the hint on the parameter is the truth.
_ARG_RE = re.compile(r"^(?P<name>\*{0,2}[A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:\s*(?P<text>.*)$")

_SCALARS: dict[str, ParameterType] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "None": "null",
    "NoneType": "null",
    "Any": "any",
}
_CONTAINERS: dict[str, str] = {
    "list": "array",
    "List": "array",
    "dict": "object",
    "Dict": "object",
}
_ITEM_TYPES = frozenset({"string", "integer", "number", "boolean", "object", "any"})

_SUPPORTED = "str, int, float, bool, list[...], dict[...], Optional[...], None, Any"


@dataclass(frozen=True)
class _Annotation:
    """An annotation resolved to a schema type."""

    type: ParameterType
    items_type: ItemType | None = None
    optional: bool = False


def extract_schema(source: str) -> ExtractionResult:
    """Read a tool out of Python source."""
    try:
        module = ast.parse(source)
    except SyntaxError as exc:
        return ExtractionResult(
            None, [f"The code does not parse: {exc.msg} (line {exc.lineno})."]
        )

    functions = [
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if not functions:
        return ExtractionResult(
            None,
            [
                "A tool is exactly one top-level function and none was found. "
                "For example: def get_weather(city: str) -> str:"
            ],
        )
    if len(functions) > 1:
        names = ", ".join(node.name for node in functions)
        return ExtractionResult(
            None,
            [
                f"A tool is exactly one top-level function; this code defines "
                f"{len(functions)}: {names}."
            ],
        )

    function = functions[0]
    if isinstance(function, ast.AsyncFunctionDef):
        return ExtractionResult(
            None, [f"`{function.name}` is async. A tool is a plain function: remove `async`."]
        )
    if len(function.name) > MAX_NAME_LENGTH:
        return ExtractionResult(
            None,
            [
                f"The function name is {len(function.name)} characters; "
                f"the limit is {MAX_NAME_LENGTH}."
            ],
        )

    docstring = ast.get_docstring(function)
    if not docstring or not docstring.strip():
        return ExtractionResult(
            None,
            [
                f"`{function.name}` has no docstring. Its first line becomes the tool "
                "description, and an `Args:` section is required."
            ],
        )

    summary = _summary(docstring)
    if not summary:
        return ExtractionResult(
            None,
            [
                f"The docstring of `{function.name}` starts with a blank line, so there is "
                "nothing to use as the tool description."
            ],
        )

    documented, section_error = _documented_arguments(docstring)
    if section_error:
        return ExtractionResult(None, [section_error])

    variadics = [
        prefix + node.arg
        for prefix, node in (("*", function.args.vararg), ("**", function.args.kwarg))
        if node is not None
    ]
    if variadics:
        return ExtractionResult(
            None,
            [
                f"{', '.join(variadics)} cannot be described to a model. A tool's "
                "parameters must be fixed; give each one a name and a type hint."
            ],
        )

    arguments = function.args.posonlyargs + function.args.args + function.args.kwonlyargs
    names = [node.arg for node in arguments]

    unannotated = [node.arg for node in arguments if node.annotation is None]
    if unannotated:
        return ExtractionResult(
            None,
            [
                "Every parameter needs a type hint. Missing on: "
                + ", ".join(f"`{name}`" for name in unannotated)
                + "."
            ],
        )

    missing_entries = [name for name in names if name not in documented]
    unknown_entries = [name for name in documented if name not in names]
    if missing_entries or unknown_entries:
        problems: list[str] = []
        if missing_entries:
            problems.append(
                "`Args:` has no entry for " + ", ".join(f"`{n}`" for n in missing_entries)
            )
        if unknown_entries:
            problems.append(
                "`Args:` names things that are not parameters: "
                + ", ".join(f"`{n}`" for n in unknown_entries)
            )
        return ExtractionResult(None, [" ".join(f"{problem}." for problem in problems)])

    # Both of these would make `ToolParameter` raise; the module returns errors
    # rather than raising, so they are checked here.
    undescribed = [name for name in names if not documented[name]]
    if undescribed:
        return ExtractionResult(
            None,
            [
                "Every parameter needs a description in `Args:`. Empty for: "
                + ", ".join(f"`{name}`" for name in undescribed)
                + "."
            ],
        )

    overlong = [name for name in names if len(name) > MAX_NAME_LENGTH]
    if overlong:
        return ExtractionResult(
            None,
            [
                f"Parameter names are limited to {MAX_NAME_LENGTH} characters. Too long: "
                + ", ".join(f"`{name}`" for name in overlong)
                + "."
            ],
        )

    resolved: dict[str, _Annotation] = {}
    undescribable: list[str] = []
    for node in arguments:
        annotation = _resolve_annotation(ast.unparse(node.annotation))
        if annotation is None:
            undescribable.append(f"`{node.arg}` (`{ast.unparse(node.annotation)}`)")
        else:
            resolved[node.arg] = annotation
    if undescribable:
        return ExtractionResult(
            None,
            [
                "Annotations that cannot be described to a model: "
                + ", ".join(undescribable)
                + f". Supported: {_SUPPORTED}."
            ],
        )

    if function.returns is None:
        return ExtractionResult(
            None,
            [f"`{function.name}` has no return annotation. Add one, e.g. `-> str`."],
        )
    returned = _resolve_annotation(ast.unparse(function.returns))
    if returned is None:
        return ExtractionResult(
            None,
            [
                "The return annotation cannot be described to a model: "
                f"`{ast.unparse(function.returns)}`. Supported: {_SUPPORTED}."
            ],
        )

    defaults = _defaults(function)
    try:
        schema = ToolSchema(
            name=function.name,
            description=summary,
            parameters=[
                ToolParameter(
                    name=node.arg,
                    type=resolved[node.arg].type,
                    description=documented[node.arg],
                    # A value the caller may leave out is not required of them.
                    required=node.arg not in defaults and not resolved[node.arg].optional,
                    items_type=resolved[node.arg].items_type,
                )
                for node in arguments
            ],
            returns=returned.type,
        )
    except ValidationError as exc:
        # Backstop for any schema constraint the checks above do not name — a
        # non-ASCII parameter name, say. The module returns errors, never raises.
        return ExtractionResult(
            None,
            [
                f"`{function.name}` cannot be described to a model: "
                + "; ".join(
                    f"{error['msg']} (at {'.'.join(str(part) for part in error['loc'])})"
                    for error in exc.errors()
                )
                + "."
            ],
        )
    return ExtractionResult(schema, [])


def compile_input_schema(schema: ToolSchema) -> dict[str, Any]:
    """The JSON Schema an LLM tool list expects for this tool's arguments."""
    properties: dict[str, Any] = {}
    for parameter in schema.parameters:
        entry: dict[str, Any] = {"type": parameter.type, "description": parameter.description}
        if parameter.type == "array":
            # No declared item type means unconstrained items: an empty schema, not
            # an absent `items` key.
            entry["items"] = {"type": parameter.items_type} if parameter.items_type else {}
        properties[parameter.name] = entry

    return {
        "type": "object",
        "properties": properties,
        "required": [parameter.name for parameter in schema.parameters if parameter.required],
        "additionalProperties": False,
    }


def _summary(docstring: str) -> str:
    """The docstring's opening paragraph: the description a model reads."""
    lines: list[str] = []
    for line in docstring.splitlines():
        stripped = line.strip()
        if not stripped or _SECTION_RE.match(stripped):
            break
        lines.append(stripped)
    return " ".join(lines).strip()


def _documented_arguments(docstring: str) -> tuple[dict[str, str], str | None]:
    """Parameter name → its `Args:` description, or why there is no section.

    `ast.get_docstring` has already dedented the block, so the `Args:` header sits
    at column 0 and its entries are indented. The first line that is not indented
    ends the section — the next header, or the resumption of prose.
    """
    lines = docstring.splitlines()
    start = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if _ARGS_HEADER_RE.match(line.strip())
        ),
        None,
    )
    if start is None:
        return {}, (
            "There is no `Args:` section. Give every parameter one "
            "`name: what it means` line beneath `Args:`."
        )

    entries: dict[str, str] = {}
    current: str | None = None
    for line in lines[start:]:
        if not line.strip():
            continue
        if not line[:1].isspace():
            break
        match = _ARG_RE.match(line.strip())
        if match:
            current = match.group("name").lstrip("*")
            entries[current] = match.group("text").strip()
        elif current is not None:
            # A wrapped description continues the entry above it.
            entries[current] = f"{entries[current]} {line.strip()}".strip()
    return entries, None


def _defaults(function: ast.FunctionDef) -> dict[str, ast.expr]:
    """Parameter name → its default node, for every parameter that has one."""
    defaults: dict[str, ast.expr] = {}
    positional = function.args.posonlyargs + function.args.args
    if function.args.defaults:
        pairs = zip(
            positional[len(positional) - len(function.args.defaults) :],
            function.args.defaults,
        )
        defaults.update({node.arg: value for node, value in pairs})
    for node, value in zip(function.args.kwonlyargs, function.args.kw_defaults):
        if value is not None:
            defaults[node.arg] = value
    return defaults


def _resolve_annotation(text: str) -> _Annotation | None:
    """Map an annotation's source text onto a schema type, or `None` if it cannot be.

    Read from `ast.unparse` output rather than from node types, so `Optional[str]`
    and `typing.Optional[str]` are the same thing once the prefix goes.
    """
    text = text.replace("typing.", "").strip()
    optional = False

    parts = [part.strip() for part in text.split("|")]
    if len(parts) > 1:
        if "None" not in parts:
            return None
        optional = True
        rest = [part for part in parts if part != "None"]
        if len(rest) != 1:
            return None
        text = rest[0]

    bracketed = re.fullmatch(r"Optional\[(.+)\]", text)
    if bracketed:
        optional = True
        text = bracketed.group(1).strip()

    subscript = re.fullmatch(r"(\w+)\[(.+)\]", text)
    if subscript:
        container = _CONTAINERS.get(subscript.group(1))
        if container is None:
            return None
        if container == "object":
            return _Annotation(type="object", optional=optional)
        item = _resolve_annotation(subscript.group(2).strip())
        if item is None:
            return None
        return _Annotation(
            type="array", items_type=_as_item_type(item.type), optional=optional
        )

    mapped = _SCALARS.get(text)
    if mapped is None:
        return None
    return _Annotation(type=mapped, optional=optional)


def _as_item_type(type_: ParameterType) -> ItemType | None:
    """An array's item type, or `None` for a type items cannot carry."""
    if type_ in _ITEM_TYPES:
        return cast(ItemType, type_)
    return None
