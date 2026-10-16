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
