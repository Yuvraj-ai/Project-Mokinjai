"""Skill reference parsing, validation and build-time compilation.

The parser is the bug-prone part: free-form markdown contains URLs, paths,
emails and code samples that all look like `@`/`/` references and are not. These
tests pin what is and is not a reference, then the graph rules built on top.

The parser and the rewriter share one scanner, which is what makes "what
validation counted" and "what a rename touches" identical.
"""

import pytest

from app.services.skill import (
    SkillDefinition,
    SkillError,
    SkillReferences,
    extract_references,
    find_skill_referrers,
    rewrite_skill_references,
    validate_skill,
)


def skill(name, description="A skill.", content="Do the thing."):
    return SkillDefinition(name=name, description=description, content=content)


def defs(*items):
    return {item.name: item for item in items}


class TestExtraction:
    def test_finds_skill_and_tool_references(self):
        refs = extract_references("Use @Writer for tone, then call /SearchWeb.")

        assert refs.skill_refs == ["Writer"]
        assert refs.tool_refs == ["SearchWeb"]

    def test_preserves_first_appearance_order(self):
        refs = extract_references("@Beta and @Alpha and /Zed then /Ann")

        assert refs.skill_refs == ["Beta", "Alpha"]
        assert refs.tool_refs == ["Zed", "Ann"]

    def test_collapses_duplicates_keeping_the_first_spelling(self):
        refs = extract_references("@Step then @step then @Step")

        assert refs.skill_refs == ["Step"]

    def test_a_reference_at_the_start_of_a_line_is_found(self):
        assert extract_references("@Writer\n\ntext").skill_refs == ["Writer"]

    def test_a_reference_inside_brackets_or_parens_is_found(self):
        refs = extract_references("(/SearchWeb) and [@Writer] and {@Writer}")

        assert refs.skill_refs == ["Writer"]
        assert refs.tool_refs == ["SearchWeb"]

    def test_an_underscore_name_is_found(self):
        assert extract_references("@My_Skill").skill_refs == ["My_Skill"]

    def test_sentence_punctuation_after_a_name_is_fine(self):
        refs = extract_references("Use @Writer. Then @Step, finally @End!")

        assert refs.skill_refs == ["Writer", "Step", "End"]


class TestFalsePositives:
    def test_a_marker_after_a_word_character_is_not_a_reference(self):
        refs = extract_references("word@Writer and word/Search")

        assert refs.skill_refs == []
        assert refs.tool_refs == []

    def test_an_email_address_is_not_a_reference(self):
        assert extract_references("Contact bob@example.com for help.").skill_refs == []

    def test_a_bare_domain_is_not_a_reference(self):
        assert extract_references("@example.com").skill_refs == []

    def test_a_url_is_not_a_tool_reference(self):
        assert extract_references("See https://example.com/path/tool for details.").tool_refs == []

    def test_a_path_is_not_a_tool_reference(self):
        assert extract_references("Run /usr/bin/env python.").tool_refs == []
        assert extract_references("cd mokinjay-project/backend").tool_refs == []
        assert extract_references("either and/or neither").tool_refs == []

    def test_an_endpoint_is_not_a_tool_reference(self):
        assert extract_references("GET /api/workspaces/one/skills").tool_refs == []

    def test_a_marker_with_no_name_is_not_a_reference(self):
        refs = extract_references("50/50 and @ and /")

        assert refs.skill_refs == []
        assert refs.tool_refs == []


class TestCodeIsSkipped:
    def test_a_fenced_block_is_not_scanned(self):
        content = "Before @Writer\n\n```python\n@decorator\ncall(/usr/bin)\n```\n\nAfter @Step\n"

        assert extract_references(content).skill_refs == ["Writer", "Step"]

    def test_a_tilde_fence_is_not_scanned(self):
        assert extract_references("~~~\n@Ghost\n~~~\n@Real\n").skill_refs == ["Real"]

    def test_an_unterminated_fence_runs_to_the_end(self):
        assert extract_references("@Real\n```\n@Ghost\n@Other\n").skill_refs == ["Real"]

    def test_an_inline_code_span_is_not_scanned(self):
        content = "Use `/usr/bin/env` and `@decorator`, but @Writer."

        assert extract_references(content).tool_refs == []
        assert extract_references(content).skill_refs == ["Writer"]

    def test_an_unterminated_inline_span_runs_to_the_end_of_the_line(self):
        assert extract_references("`@Ghost and @Writer\n@Real").skill_refs == ["Real"]


class TestValidation:
    def test_a_valid_skill_passes(self):
        writer = skill("Writer", content="Follow @Step. Call /SearchWeb.")

        validate_skill(writer, defs(skill("Step"), writer), known_tools=["SearchWeb"])

    def test_an_unresolved_skill_reference_is_rejected(self):
        writer = skill("Writer", content="Use @Ghost.")

        with pytest.raises(SkillError) as excinfo:
            validate_skill(writer, defs(writer), known_tools=[])

        assert "Ghost" in str(excinfo.value)

    def test_an_unresolved_tool_reference_is_rejected(self):
        writer = skill("Writer", content="Call /SearchWeb.")

        with pytest.raises(SkillError) as excinfo:
            validate_skill(writer, defs(writer), known_tools=["Other"])

        assert "SearchWeb" in str(excinfo.value)
        assert "Writer" in str(excinfo.value)

    def test_a_resolved_tool_reference_passes_case_insensitively(self):
        writer = skill("Writer", content="Call /SearchWeb.")

        validate_skill(writer, defs(writer), known_tools=["searchweb"])

    def test_a_sub_skill_reference_resolves_case_insensitively(self):
        writer = skill("Writer", content="Follow @step.")

        validate_skill(writer, defs(skill("Step"), writer), known_tools=[])

    def test_a_missing_description_is_rejected(self):
        writer = skill("Writer", description="   ")

        with pytest.raises(SkillError) as excinfo:
            validate_skill(writer, defs(writer), known_tools=[])

        assert "Writer" in str(excinfo.value)

    def test_empty_content_is_rejected(self):
        writer = skill("Writer", content="")

        with pytest.raises(SkillError):
            validate_skill(writer, defs(writer), known_tools=[])

    def test_a_fenced_example_is_not_validated(self):
        writer = skill("Writer", content="An example:\n\n```\n@Ghost and /GhostTool\n```\n")

        validate_skill(writer, defs(writer), known_tools=[])


class TestCycles:
    def test_a_self_reference_is_a_cycle(self):
        loop = skill("Loop", content="Then read @Loop.")

        with pytest.raises(SkillError) as excinfo:
            validate_skill(loop, defs(loop), known_tools=[])

        assert str(excinfo.value) == "Circular reference: Loop → Loop"

    def test_a_mutual_cycle_names_the_path(self):
        alpha = skill("Alpha", content="Then @Beta.")
        beta = skill("Beta", content="Then @Alpha.")

        with pytest.raises(SkillError) as excinfo:
            validate_skill(alpha, defs(alpha, beta), known_tools=[])

        assert str(excinfo.value) == "Circular reference: Alpha → Beta → Alpha"

    def test_a_longer_cycle_is_detected(self):
        a = skill("A", content="@B")
        b = skill("B", content="@C")
        c = skill("C", content="@A")

        with pytest.raises(SkillError):
            validate_skill(a, defs(a, b, c), known_tools=[])

    def test_a_cycle_through_a_sub_skill_is_detected(self):
        root = skill("Root", content="@Mid")
        mid = skill("Mid", content="@Root")

        with pytest.raises(SkillError) as excinfo:
            validate_skill(root, defs(root, mid), known_tools=[])

        assert "Root" in str(excinfo.value) and "→" in str(excinfo.value)

    def test_a_diamond_is_not_a_cycle(self):
        unit = skill("Unit")
        left = skill("Left", content="@Unit")
        right = skill("Right", content="@Unit")
        root = skill("Root", content="@Left and @Right")

        validate_skill(root, defs(unit, left, right, root), known_tools=[])


class TestReferrers:
    def test_returns_every_direct_referrer(self):
        step = skill("Step")
        alpha = skill("Alpha", content="@Step")
        beta = skill("Beta", content="and @Step.")
        other = skill("Other", content="nothing here")

        assert find_skill_referrers("Step", defs(step, alpha, beta, other)) == ["Alpha", "Beta"]

    def test_matches_case_insensitively(self):
        step = skill("Step")
        alpha = skill("Alpha", content="@step")

        assert find_skill_referrers("STEP", defs(step, alpha)) == ["Alpha"]

    def test_returns_nothing_when_unreferenced(self):
        assert find_skill_referrers("Lonely", defs(skill("Lonely"))) == []


class TestRename:
    def test_rewrites_a_reference_keeping_the_marker(self):
        content = "Use @Step then @Step again."

        assert rewrite_skill_references(content, "Step", "SolutionStep") == (
            "Use @SolutionStep then @SolutionStep again."
        )

    def test_rewrites_case_insensitively(self):
        assert rewrite_skill_references("see @step", "Step", "SolutionStep") == "see @SolutionStep"

    def test_leaves_a_fenced_example_alone(self):
        content = "Use @Step.\n\n```\n@Step inside code\n```\n"

        assert rewrite_skill_references(content, "Step", "SolutionStep") == (
            "Use @SolutionStep.\n\n```\n@Step inside code\n```\n"
        )

    def test_leaves_an_inline_code_span_alone(self):
        content = "Use @Step, or write `@Step` in code."

        assert rewrite_skill_references(content, "Step", "SolutionStep") == (
            "Use @SolutionStep, or write `@Step` in code."
        )

    def test_leaves_tool_references_alone(self):
        assert rewrite_skill_references("@Step uses /Step", "Step", "SolutionStep") == (
            "@SolutionStep uses /Step"
        )

    def test_touches_nothing_when_there_is_no_reference(self):
        assert rewrite_skill_references("plain text", "Step", "SolutionStep") == "plain text"
