"""Slice 3: resolve an agent's skills, tools and subagent graph.

Pure module: rows are reduced to plain values before they get here.
"""

import pytest

from app.services.agent_dependencies import (
    SubagentGraphError,
    effective_tool_names,
    resolve_skills,
    validate_subagent_selection,
)
from app.services.skill import SkillDefinition

SKILLS = {
    "SkillA": SkillDefinition(
        name="SkillA",
        description="Top level",
        content="Use /Tool1 and /Tool2, then @SkillB.",
    ),
    "SkillB": SkillDefinition(
        name="SkillB",
        description="Nested",
        content="Use /Tool3.",
    ),
    "SkillC": SkillDefinition(
        name="SkillC",
        description="Independent",
        content="Use /Tool1.",
    ),
}


class TestSkillResolution:
    def test_closure_includes_nested_skills_and_tools(self):
        resolved = resolve_skills(["SkillA"], SKILLS)
        assert resolved.skill_closure == ("SkillA", "SkillB")
        assert resolved.tool_names == ("Tool1", "Tool2", "Tool3")

    def test_menu_lists_only_the_selected_roots(self):
        resolved = resolve_skills(["SkillA"], SKILLS)
        assert [entry.name for entry in resolved.menu] == ["SkillA"]

    def test_selection_is_case_insensitive(self):
        resolved = resolve_skills(["skilla"], SKILLS)
        assert resolved.skill_closure == ("SkillA", "SkillB")

    def test_two_roots_share_dependencies_without_duplicates(self):
        resolved = resolve_skills(["SkillA", "SkillC"], SKILLS)
        assert resolved.skill_closure == ("SkillA", "SkillB", "SkillC")
        assert resolved.tool_names == ("Tool1", "Tool2", "Tool3")

    def test_unknown_skill_is_reported(self):
        with pytest.raises(Exception) as exc:
            resolve_skills(["Missing"], SKILLS)
        assert "Missing" in str(exc.value)

    def test_no_skills_is_empty(self):
        resolved = resolve_skills([], SKILLS)
        assert resolved.skill_closure == ()
        assert resolved.tool_names == ()


class TestEffectiveTools:
    def test_union_of_skill_tools_and_direct_tools(self):
        assert effective_tool_names(["Tool1", "Tool2"], ["Tool9"]) == (
            "Tool1",
            "Tool2",
            "Tool9",
        )

    def test_deduplicates_case_insensitively_keeping_the_direct_name(self):
        assert effective_tool_names(["tool1"], ["Tool1"]) == ("Tool1",)

    def test_skill_tools_cannot_be_removed(self):
        effective = effective_tool_names(["Tool1"], [])
        assert "Tool1" in effective


class TestSubagentGraph:
    def test_an_agent_may_name_itself_only_if_it_is_not_itself(self):
        with pytest.raises(SubagentGraphError) as exc:
            validate_subagent_selection("a", ["a"], {}, known_ids={"a"})
        assert "itself" in str(exc.value).lower()

    def test_unknown_subagent_is_reported(self):
        with pytest.raises(SubagentGraphError) as exc:
            validate_subagent_selection("a", ["missing"], {}, known_ids={"a"})
        assert "missing" in str(exc.value)

    def test_a_direct_cycle_is_reported_with_the_path(self):
        edges = {"b": ["a"]}
        with pytest.raises(SubagentGraphError) as exc:
            validate_subagent_selection("a", ["b"], edges, known_ids={"a", "b"})
        assert "a" in str(exc.value) and "b" in str(exc.value)

    def test_a_longer_cycle_is_reported(self):
        edges = {"b": ["c"], "c": ["a"]}
        with pytest.raises(SubagentGraphError):
            validate_subagent_selection("a", ["b"], edges, known_ids={"a", "b", "c"})

    def test_three_levels_are_allowed(self):
        edges = {"b": ["c"]}
        validate_subagent_selection("a", ["b"], edges, known_ids={"a", "b", "c"})

    def test_four_levels_are_refused(self):
        edges = {"b": ["c"], "c": ["d"]}
        with pytest.raises(SubagentGraphError) as exc:
            validate_subagent_selection("a", ["b"], edges, known_ids={"a", "b", "c", "d", "e"}, max_depth=3)
        assert "depth" in str(exc.value).lower() or "deep" in str(exc.value).lower()

    def test_a_diamond_is_not_a_cycle(self):
        edges = {"b": ["d"], "c": ["d"]}
        validate_subagent_selection("a", ["b", "c"], edges, known_ids={"a", "b", "c", "d"})

    def test_existing_edges_for_the_saved_agent_are_replaced_not_merged(self):
        # Saving a with no subagents must clear the old edge a -> b.
        validate_subagent_selection("a", [], {"a": ["b"]}, known_ids={"a", "b"})
