"""Build-time dependency resolution for an agent.

Pure module: callers reduce ORM rows to names and `SkillDefinition` values before
they arrive here. Two graphs are handled:

- Skills: selected roots expand to their recursive `@` closure, and the union of
  their `/` tool references is the locked part of the tool set (ADR-021).
- Subagents: a directed graph of agents. Cycles and chains deeper than the
  configured limit are refused before anything is written.

Tools are derived, never stored as a resolved set (ADR-016).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.services.skill import MenuEntry, SkillDefinition, compile_skills

DEFAULT_MAX_SUBAGENT_DEPTH = 3


class SubagentGraphError(Exception):
    """A subagent selection would create an invalid graph."""


@dataclass(frozen=True)
class ResolvedSkills:
    menu: tuple[MenuEntry, ...]
    skill_closure: tuple[str, ...]
    contents: dict[str, str]
    tool_names: tuple[str, ...]


def resolve_skills(
    selected: Sequence[str], skills: Mapping[str, SkillDefinition]
) -> ResolvedSkills:
    """Expand the selected skills to their recursive closure and tool union."""
    compiled = compile_skills(selected, skills)
    return ResolvedSkills(
        menu=tuple(compiled.menu),
        skill_closure=tuple(compiled.contents),
        contents=dict(compiled.contents),
        tool_names=tuple(compiled.tool_names),
    )


def effective_tool_names(
    required: Sequence[str], direct: Sequence[str]
) -> tuple[str, ...]:
    """Union of skill-required and directly selected tools.

    A direct selection may fix the casing of a required name, but it can never
    remove it: the caller's accepted set is required ∪ direct.
    """
    canonical: dict[str, str] = {}
    for name in required:
        canonical.setdefault(name.lower(), name)
    for name in direct:
        canonical[name.lower()] = name

    ordered: list[str] = []
    for name in [*required, *direct]:
        key = name.lower()
        if key in canonical and canonical[key] not in ordered:
            ordered.append(canonical[key])
    return tuple(ordered)


def validate_subagent_selection(
    agent_id: str,
    selected: Sequence[str],
    existing_edges: Mapping[str, Iterable[str]],
    *,
    known_ids: set[str],
    max_depth: int = DEFAULT_MAX_SUBAGENT_DEPTH,
) -> None:
    """Refuse self-reference, missing agents, cycles and over-deep chains.

    `existing_edges` is the saved graph; the agent's own edges are replaced by
    `selected`, so clearing the selection clears the old links.
    """
    chosen = list(dict.fromkeys(selected))

    if agent_id in chosen:
        raise SubagentGraphError("an agent cannot select itself as a subagent")
    missing = [name for name in chosen if name not in known_ids]
    if missing:
        raise SubagentGraphError(
            "unknown subagent: " + ", ".join(sorted(missing))
        )

    graph = {node: list(children) for node, children in existing_edges.items()}
    graph[agent_id] = chosen

    depth = _walk(agent_id, graph, [])
    if depth > max_depth:
        raise SubagentGraphError(
            f"subagent chain is {depth} levels deep; the maximum is {max_depth}"
        )


def _walk(node: str, graph: Mapping[str, Sequence[str]], path: list[str]) -> int:
    if node in path:
        cycle = path[path.index(node) :] + [node]
        raise SubagentGraphError("subagent cycle: " + " → ".join(cycle))

    next_path = [*path, node]
    depth = 1
    for child in graph.get(node, []):
        depth = max(depth, 1 + _walk(child, graph, next_path))
    return depth
