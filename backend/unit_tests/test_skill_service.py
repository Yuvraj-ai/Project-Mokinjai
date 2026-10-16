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
