"""Skill reference parsing, validation and build-time compilation.

Pure module: it never touches the database and no ORM object crosses into it.
Callers reduce their rows to `SkillDefinition` objects, which is also what tests
build directly.

It is the sibling of `app/services/structured_output.py`. That module walks a
reference graph forward from the definition being written and reports a cycle
with the path named (`MathReasoning → Step → MathReasoning`); this one does the
same over `@` skill references.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Iterator, Mapping


class SkillError(Exception):
    """A skill cannot be saved, or its reference graph cannot be resolved."""


@dataclass(frozen=True)
class SkillDefinition:
    """A skill, reduced to what parsing and compilation need."""

    name: str
    description: str
    content: str


@dataclass(frozen=True)
class SkillReferences:
    """What a skill's markdown points at, in first-appearance order."""

    skill_refs: list[str]
    tool_refs: list[str]


@dataclass(frozen=True)
class _Match:
    """One recognised reference, with the offsets a rename splices on."""

    kind: str   # "skill" or "tool"
    name: str
    start: int  # index of the marker character
    end: int    # index just past the name


_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_OPENERS = "([{"
_FENCES = ("```", "~~~")


# --------------------------------------------------------------------------- #
# The scanner
# --------------------------------------------------------------------------- #


def _scan(content: str) -> Iterator[_Match]:
    """Every `@Skill` and `/Tool` reference, skipping code.

    The rename path uses this same scanner, so a rename can never touch text the
    validator did not count as a reference.
    """
    offset = 0
    fence: str | None = None
    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        if fence is None:
            if stripped[:3] in _FENCES:
                fence = stripped[:3]
            else:
                yield from _scan_line(line, offset)
        elif stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
            fence = None
        offset += len(line)


def _scan_line(line: str, base: int) -> Iterator[_Match]:
    index = 0
    length = len(line)
    while index < length:
        char = line[index]
        if char == "`":
            run = _run_length(line, index)
            close = _find_closing_run(line, index + run, run)
            if close == -1:
                return  # an unterminated span runs to the end of the line
            index = close + run
            continue
        if char in "@/":
            name = _name_at(line, index)
            if name is not None:
                yield _Match(
                    kind="skill" if char == "@" else "tool",
                    name=name,
                    start=base + index,
                    end=base + index + 1 + len(name),
                )
                index += 1 + len(name)
                continue
        index += 1


def _name_at(line: str, index: int) -> str | None:
    """The reference name at a marker, or None when this marker is not one.

    Three rules, each aimed at a real false positive:

    - context: the marker must follow the start of the line, whitespace, or an
      opening bracket. This is what keeps `bob@example.com` and `https://…` out.
    - name: a reference is `[A-Za-z][A-Za-z0-9_]*` — a bare `/` is not one.
    - trailing: a name followed by `/` is a path (`/usr/bin`, `/api/v1`), and a
      name followed by `.` and a letter is an address (`@example.com`).
    """
    if index > 0:
        previous = line[index - 1]
        if not (previous.isspace() or previous in _OPENERS):
            return None

    rest = line[index + 1 :]
    match = _NAME_RE.match(rest)
    if match is None:
        return None
    name = match.group(0)

    tail = rest[len(name) :]
    if tail.startswith("/"):
        return None
    if tail[:1] == "." and len(tail) > 1 and tail[1].isalnum():
        return None
    return name


def _run_length(line: str, index: int) -> int:
    """How many identical characters start at `index`."""
    char = line[index]
    run = 0
    while index + run < len(line) and line[index + run] == char:
        run += 1
    return run


def _find_closing_run(line: str, start: int, size: int) -> int:
    """The index of a run of exactly `size` backticks at or after `start`, or -1."""
    index = start
    while index < len(line):
        if line[index] != "`":
            index += 1
            continue
        run = _run_length(line, index)
        if run == size:
            return index
        index += run
    return -1


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


def extract_references(content: str) -> SkillReferences:
    """Every `@Skill` and `/Tool` a markdown body points at.

    Names come back in first-appearance order, de-duplicated case-insensitively
    (the first spelling wins). A marker inside a fenced block or an inline code
    span is not a reference, and neither is a `/` in a URL or a path or an `@`
    in an email address.
    """
    skills: dict[str, str] = {}
    tools: dict[str, str] = {}
    for match in _scan(content):
        bucket = skills if match.kind == "skill" else tools
        bucket.setdefault(match.name.lower(), match.name)
    return SkillReferences(skill_refs=list(skills.values()), tool_refs=list(tools.values()))


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def validate_skill(
    definition: SkillDefinition,
    workspace_skills: Mapping[str, SkillDefinition],
    known_tools: Iterable[str],
) -> None:
    """Raise `SkillError` unless the skill can be saved.

    Unresolved `@` and `/` references, cycles and a self-reference are all caught
    here. `workspace_skills` is every skill in the workspace keyed by name, so
    the graph is walked without this module reading a row: callers reduce rows to
    `SkillDefinition`s, and tests build them directly.
    """
    if not definition.name.strip():
        raise SkillError("A skill needs a name.")
    if not definition.description.strip():
        raise SkillError(
            f"'{definition.name}' needs a description. It is the menu line the model sees."
        )
    if not definition.content.strip():
        raise SkillError(f"'{definition.name}' has no content.")

    _reachable(definition, workspace_skills)

    tools = {name.lower() for name in known_tools}
    for name in extract_references(definition.content).tool_refs:
        if name.lower() not in tools:
            raise SkillError(
                f"'{definition.name}' references the tool '{name}', which is not a tool "
                "in this workspace. Add the tool first, then reference it."
            )


def _lookup(name: str, workspace_skills: Mapping[str, SkillDefinition]) -> SkillDefinition:
    wanted = name.lower()
    for key, definition in workspace_skills.items():
        if key.lower() == wanted:
            return definition
    raise SkillError(
        f"'{name}' is not a skill in this workspace, so it cannot be referenced."
    )


def _reachable(
    root: SkillDefinition, workspace_skills: Mapping[str, SkillDefinition]
) -> list[SkillDefinition]:
    """Walk forward from `root`, collecting the transitive `@` closure.

    Reaching a skill that is already on the current path is a cycle, and the
    error names the path so the user can see the loop they built. A self-reference
    is the degenerate case of the same walk, so it needs no special case.
    """
    collected: dict[str, SkillDefinition] = {}

    def walk(definition: SkillDefinition, path: list[str]) -> None:
        for name in extract_references(definition.content).skill_refs:
            target = _lookup(name, workspace_skills)
            if target.name in path:
                raise SkillError("Circular reference: " + " → ".join([*path, target.name]))
            if target.name in collected:
                continue
            collected[target.name] = target
            walk(target, [*path, target.name])

    walk(root, [root.name])
    collected.pop(root.name, None)
    return list(collected.values())


def find_skill_referrers(
    name: str, workspace_skills: Mapping[str, SkillDefinition]
) -> list[str]:
    """Names of every skill whose content references `name` with an `@`."""
    wanted = name.lower()
    return sorted(
        other.name
        for other in workspace_skills.values()
        if any(ref.lower() == wanted for ref in extract_references(other.content).skill_refs)
    )


def rewrite_skill_references(content: str, old_name: str, new_name: str) -> str:
    """Point every `@old_name` at `@new_name`. ADR-019: references are by name.

    Rewrites only what the scanner recognises as a reference, so an `@old_name`
    inside a code fence — an example, not a reference — is left exactly as the
    author wrote it.
    """
    wanted = old_name.lower()
    pieces: list[str] = []
    cursor = 0
    for match in _scan(content):
        if match.kind != "skill" or match.name.lower() != wanted:
            continue
        pieces.append(content[cursor : match.start])
        pieces.append(f"@{new_name}")
        cursor = match.end
    pieces.append(content[cursor:])
    return "".join(pieces)


# --------------------------------------------------------------------------- #
# Build-time compilation
# --------------------------------------------------------------------------- #

DEFAULT_READ_SKILL_TOOL = "read_skill"


@dataclass(frozen=True)
class MenuEntry:
    """One line of the menu the LLM sees at startup."""

    name: str
    description: str

    def line(self) -> str:
        return f"- {self.name}: {self.description}"


@dataclass(frozen=True)
class CompiledSkills:
    """What a set of assigned skills contributes to an agent build.

    This is the contract the agent runtime consumes. Nothing here executes: the
    runtime that registers `read_skill_tool` and injects `menu_text()` into the
    system prompt belongs to the agent runtime, not to Skills.
    """

    menu: list[MenuEntry]
    contents: dict[str, str]
    tool_names: list[str]
    read_skill_tool: str

    def menu_text(self) -> str:
        return "\n".join(entry.line() for entry in self.menu)


def compile_skills(
    root_names: Iterable[str],
    workspace_skills: Mapping[str, SkillDefinition],
    *,
    read_skill_tool: str = DEFAULT_READ_SKILL_TOOL,
) -> CompiledSkills:
    """Everything an agent build takes from a set of assigned skills.

    Skills do not execute; they contribute context. Three properties are the
    contract:

    - `menu` lists only the assigned skills. A skill reached by `@` is discovered
      by reading a parent's content, where the pointer is visible, not from the
      menu; listing it would grow the startup prompt with the whole closure.
    - `contents` is the whole reachable closure, which is the scope `read_skill`
      may serve. A name outside it must be refused (ADR-016). It is keyed by each
      skill's canonical `name`, and a `@` reference resolves case-insensitively,
      so a consumer must resolve the name first.
    - `tool_names` is the union of `/` references across that closure, because
      tools are never lazy: when the LLM reads a sub-skill that depends on a
      tool, that tool must already be in the tool list.
    """
    menu: list[MenuEntry] = []
    contents: dict[str, str] = {}
    tool_names: dict[str, str] = {}

    for root_name in root_names:
        root = _lookup(root_name, workspace_skills)
        menu.append(MenuEntry(name=root.name, description=root.description))
        for definition in [root, *_reachable(root, workspace_skills)]:
            contents.setdefault(definition.name, definition.content)
            for name in extract_references(definition.content).tool_refs:
                tool_names.setdefault(name.lower(), name)

    return CompiledSkills(
        menu=menu,
        contents=contents,
        tool_names=sorted(tool_names.values(), key=str.lower),
        read_skill_tool=read_skill_tool,
    )
