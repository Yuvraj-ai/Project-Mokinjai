"""Structured output compiler and paste parser.

Fields are canonical: paste mode converts JSON Schema into fields, and the
compiler generates JSON Schema back out. These tests cover both directions plus
reference resolution, which is what makes composition safe.
"""

import json

import pytest

from app.services.structured_output import (
    Definition,
    StructuredOutputError,
    compile_schema,
    find_referrers,
    parse_json_schema,
)


def field(name, type_, description="What goes here.", required=True, **extra):
    return {"name": name, "type": type_, "description": description, "required": required, **extra}


def definition(**kwargs):
    kwargs.setdefault("description", "A shape.")
    return Definition(**kwargs)


def defs(*items):
    return {item.name: item for item in items}


# --------------------------------------------------------------------------- #
# Compilation
# --------------------------------------------------------------------------- #


class TestScalarCompilation:
    @pytest.mark.parametrize(
        "declared,expected",
        [
            ("string", "string"),
            ("number", "number"),
            ("integer", "integer"),
            ("boolean", "boolean"),
        ],
    )
    def test_scalar_types_map_to_their_json_schema_type(self, declared, expected):
        root = definition(name="Answer", fields=[field("value", declared)])

        schema = compile_schema(root, defs(root))

        assert schema["properties"]["value"]["type"] == expected
        assert schema["properties"]["value"]["description"] == "What goes here."

    def test_any_omits_the_type_constraint(self):
        root = definition(name="Answer", fields=[field("value", "any")])

        schema = compile_schema(root, defs(root))

        assert "type" not in schema["properties"]["value"]
        assert schema["properties"]["value"]["description"] == "What goes here."

    def test_root_carries_title_description_and_object_type(self):
        root = definition(
            name="MathReasoning",
            description="Reasoning steps, then the answer.",
            fields=[field("answer", "string")],
        )

        schema = compile_schema(root, defs(root))

        assert schema["title"] == "MathReasoning"
        assert schema["description"] == "Reasoning steps, then the answer."
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False

    def test_required_is_a_subset_listed_in_field_order(self):
        root = definition(
            name="Answer",
            fields=[
                field("first", "string"),
                field("optional_note", "string", required=False),
                field("last", "integer"),
            ],
        )

        schema = compile_schema(root, defs(root))

        assert schema["required"] == ["first", "last"]
        assert list(schema["properties"].keys()) == ["first", "optional_note", "last"]


class TestListCompilation:
    def test_list_of_scalar_becomes_an_array(self):
        root = definition(name="Answer", fields=[field("tags", "list", items_type="string")])

        schema = compile_schema(root, defs(root))

        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["tags"]["items"] == {"type": "string"}

    @pytest.mark.parametrize("scalar", ["string", "number", "integer", "boolean"])
    def test_every_scalar_works_as_a_list_item(self, scalar):
        root = definition(name="Answer", fields=[field("values", "list", items_type=scalar)])

        schema = compile_schema(root, defs(root))

        assert schema["properties"]["values"]["items"]["type"] == scalar

    def test_list_of_any_items_omit_the_type_constraint(self):
        root = definition(name="Answer", fields=[field("blobs", "list", items_type="any")])

        schema = compile_schema(root, defs(root))

        assert schema["properties"]["blobs"]["items"] == {}


class TestReferenceCompilation:
    def test_reference_type_compiles_to_a_ref(self):
        unit = definition(name="Unit", fields=[field("symbol", "string")])
        root = definition(name="Step", fields=[field("unit", "reference", ref="Unit")])

        schema = compile_schema(root, defs(unit, root))

        assert schema["properties"]["unit"]["$ref"] == "#/$defs/Unit"
        assert schema["properties"]["unit"]["description"] == "What goes here."

    def test_list_of_reference_compiles_to_an_array_of_ref(self):
        step = definition(name="Step", fields=[field("text", "string")])
        root = definition(name="Plan", fields=[field("steps", "list", items_type="reference", items_ref="Step")])

        schema = compile_schema(root, defs(step, root))

        assert schema["properties"]["steps"]["items"] == {"$ref": "#/$defs/Step"}

    def test_defs_include_the_transitive_closure(self):
        unit = definition(name="Unit", fields=[field("symbol", "string")])
        step = definition(name="Step", fields=[field("unit", "reference", ref="Unit")])
        root = definition(name="Plan", fields=[field("steps", "list", items_type="reference", items_ref="Step")])

        schema = compile_schema(root, defs(unit, step, root))

        assert set(schema["$defs"]) == {"Step", "Unit"}

    def test_defs_are_deduplicated_across_fields(self):
        step = definition(name="Step", fields=[field("text", "string")])
        root = definition(
            name="Plan",
            fields=[
                field("steps", "list", items_type="reference", items_ref="Step"),
                field("fallback", "reference", ref="Step"),
            ],
        )

        schema = compile_schema(root, defs(step, root))

        assert list(schema["$defs"]) == ["Step"]

    def test_the_root_is_not_repeated_inside_defs(self):
        root = definition(name="Plan", fields=[field("answer", "string")])

        schema = compile_schema(root, defs(root))

        assert schema["$defs"] == {}

    def test_every_object_forbids_additional_properties(self):
        step = definition(name="Step", fields=[field("text", "string")])
        root = definition(name="Plan", fields=[field("steps", "reference", ref="Step")])

        schema = compile_schema(root, defs(step, root))

        assert schema["$defs"]["Step"]["additionalProperties"] is False


class TestCompilationFailures:
    def test_unresolved_reference_names_the_missing_target(self):
        root = definition(name="Plan", fields=[field("steps", "reference", ref="Ghost")])

        with pytest.raises(StructuredOutputError) as excinfo:
            compile_schema(root, defs(root))

        assert "Ghost" in str(excinfo.value)

    def test_self_reference_is_a_cycle(self):
        root = definition(name="Loop", fields=[field("next", "reference", ref="Loop")])

        with pytest.raises(StructuredOutputError) as excinfo:
            compile_schema(root, defs(root))

        assert "Loop" in str(excinfo.value)

    def test_mutual_reference_is_a_cycle_from_either_side(self):
        alpha = definition(name="Alpha", fields=[field("beta", "reference", ref="Beta")])
        beta = definition(name="Beta", fields=[field("alpha", "reference", ref="Alpha")])
        workspace = defs(alpha, beta)

        with pytest.raises(StructuredOutputError):
            compile_schema(alpha, workspace)
        with pytest.raises(StructuredOutputError):
            compile_schema(beta, workspace)

    def test_cycle_message_shows_the_path(self):
        alpha = definition(name="Alpha", fields=[field("beta", "reference", ref="Beta")])
        beta = definition(name="Beta", fields=[field("alpha", "reference", ref="Alpha")])

        with pytest.raises(StructuredOutputError) as excinfo:
            compile_schema(alpha, defs(alpha, beta))

        message = str(excinfo.value)
        assert "Alpha" in message and "Beta" in message
        assert "→" in message

    def test_longer_cycle_is_detected(self):
        a = definition(name="A", fields=[field("b", "reference", ref="B")])
        b = definition(name="B", fields=[field("c", "reference", ref="C")])
        c = definition(name="C", fields=[field("a", "reference", ref="A")])

        with pytest.raises(StructuredOutputError):
            compile_schema(a, defs(a, b, c))

    def test_a_diamond_is_not_a_cycle(self):
        unit = definition(name="Unit", fields=[field("symbol", "string")])
        left = definition(name="Left", fields=[field("unit", "reference", ref="Unit")])
        right = definition(name="Right", fields=[field("unit", "reference", ref="Unit")])
        root = definition(
            name="Root",
            fields=[
                field("left", "reference", ref="Left"),
                field("right", "reference", ref="Right"),
            ],
        )

        schema = compile_schema(root, defs(unit, left, right, root))

        assert set(schema["$defs"]) == {"Left", "Right", "Unit"}


class TestFindReferrers:
    def test_returns_every_definition_that_references_the_name(self):
        unit = definition(name="Unit", fields=[field("symbol", "string")])
        step = definition(name="Step", fields=[field("unit", "reference", ref="Unit")])
        plan = definition(name="Plan", fields=[field("steps", "list", items_type="reference", items_ref="Unit")])
        other = definition(name="Other", fields=[field("answer", "string")])

        referrers = find_referrers("Unit", defs(unit, step, plan, other))

        assert sorted(referrers) == ["Plan", "Step"]

    def test_returns_nothing_when_unreferenced(self):
        lonely = definition(name="Lonely", fields=[field("answer", "string")])

        assert find_referrers("Lonely", defs(lonely)) == []

    def test_matches_the_reference_case_insensitively(self):
        step = definition(name="Step", fields=[field("unit", "reference", ref="Unit")])

        assert find_referrers("unit", defs(step)) == ["Step"]


# --------------------------------------------------------------------------- #
# Paste parsing
# --------------------------------------------------------------------------- #


class TestParseAccepts:
    def test_object_with_scalars_becomes_fields(self):
        raw = json.dumps(
            {
                "title": "MathReasoning",
                "description": "Reasoning steps, then the answer.",
                "type": "object",
                "properties": {
                    "answer": {"type": "string", "description": "The final answer."},
                    "confidence": {"type": "number", "description": "0 to 1."},
                },
                "required": ["answer"],
            }
        )

        parsed = parse_json_schema(raw, existing_names=set())

        assert [f.name for f in parsed.fields] == ["answer", "confidence"]
        assert parsed.fields[0].required is True
        assert parsed.fields[1].required is False
        assert parsed.fields[0].description == "The final answer."
        assert parsed.title == "MathReasoning"
        assert parsed.description == "Reasoning steps, then the answer."

    def test_property_order_is_preserved(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {
                    "zebra": {"type": "string", "description": "z"},
                    "alpha": {"type": "string", "description": "a"},
                },
            }
        )

        parsed = parse_json_schema(raw, existing_names=set())

        assert [f.name for f in parsed.fields] == ["zebra", "alpha"]

    def test_array_of_scalar_becomes_a_list_field(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {"tags": {"type": "array", "items": {"type": "string"}, "description": "Tags."}},
            }
        )

        parsed = parse_json_schema(raw, existing_names=set())

        assert parsed.fields[0].type == "list"
        assert parsed.fields[0].items_type == "string"

    def test_ref_to_a_saved_definition_becomes_a_reference_field(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {"step": {"$ref": "#/$defs/Step", "description": "The step."}},
            }
        )

        parsed = parse_json_schema(raw, existing_names={"Step"})

        assert parsed.fields[0].type == "reference"
        assert parsed.fields[0].ref == "Step"

    def test_array_of_ref_becomes_a_list_of_references(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {
                    "steps": {"type": "array", "items": {"$ref": "#/$defs/Step"}, "description": "The steps."}
                },
            }
        )

        parsed = parse_json_schema(raw, existing_names={"Step"})

        assert parsed.fields[0].type == "list"
        assert parsed.fields[0].items_type == "reference"
        assert parsed.fields[0].items_ref == "Step"

    def test_any_style_schema_becomes_an_unconstrained_field(self):
        raw = json.dumps({"type": "object", "properties": {"blob": {"description": "Anything."}}})

        parsed = parse_json_schema(raw, existing_names=set())

        assert parsed.fields[0].type == "any"

    def test_additional_properties_and_schema_are_tolerated(self):
        raw = json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "additionalProperties": False,
                "properties": {"answer": {"type": "string", "description": "The answer."}},
            }
        )

        parsed = parse_json_schema(raw, existing_names=set())

        assert parsed.fields[0].name == "answer"

    def test_missing_title_and_description_come_back_empty(self):
        raw = json.dumps({"type": "object", "properties": {"a": {"type": "string", "description": "A."}}})

        parsed = parse_json_schema(raw, existing_names=set())

        assert parsed.title is None
        assert parsed.description is None


class TestParseRejects:
    def test_invalid_json_is_rejected(self):
        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema("{not json", existing_names=set())

        assert "JSON" in str(excinfo.value)

    def test_non_object_root_is_rejected(self):
        with pytest.raises(StructuredOutputError):
            parse_json_schema(json.dumps({"type": "string"}), existing_names=set())

    def test_object_without_properties_is_rejected(self):
        with pytest.raises(StructuredOutputError):
            parse_json_schema(json.dumps({"type": "object", "properties": {}}), existing_names=set())

    @pytest.mark.parametrize(
        "keyword,value",
        [
            ("enum", ["a", "b"]),
            ("const", "fixed"),
            ("oneOf", [{"type": "string"}]),
            ("anyOf", [{"type": "string"}]),
            ("allOf", [{"type": "string"}]),
            ("not", {"type": "string"}),
        ],
    )
    def test_composition_keywords_are_rejected_by_name(self, keyword, value):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {"answer": {"type": "string", keyword: value, "description": "The answer."}},
            }
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert keyword in str(excinfo.value)
        assert "answer" in str(excinfo.value)

    @pytest.mark.parametrize(
        "keyword,value",
        [
            ("minimum", 0),
            ("maximum", 10),
            ("minLength", 1),
            ("maxLength", 10),
            ("pattern", "^a"),
            ("format", "email"),
            ("minItems", 1),
            ("maxItems", 5),
            ("uniqueItems", True),
        ],
    )
    def test_validation_keywords_are_rejected_by_name(self, keyword, value):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {"answer": {"type": "string", keyword: value, "description": "The answer."}},
            }
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert keyword in str(excinfo.value)

    def test_inline_nested_object_is_rejected(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {
                    "inner": {
                        "type": "object",
                        "properties": {"deep": {"type": "string", "description": "Deep."}},
                        "description": "Nested.",
                    }
                },
            }
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert "inner" in str(excinfo.value)

    def test_tuple_array_is_rejected(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "array",
                        "items": [{"type": "string"}, {"type": "number"}],
                        "description": "A pair.",
                    }
                },
            }
        )

        with pytest.raises(StructuredOutputError):
            parse_json_schema(raw, existing_names=set())

    def test_nested_array_is_rejected(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {
                    "grid": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                        "description": "A grid.",
                    }
                },
            }
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert "grid" in str(excinfo.value)

    def test_array_without_items_is_rejected(self):
        raw = json.dumps(
            {"type": "object", "properties": {"things": {"type": "array", "description": "Things."}}}
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert "things" in str(excinfo.value)

    def test_pattern_properties_is_rejected(self):
        raw = json.dumps(
            {"type": "object", "properties": {"a": {"type": "string", "description": "A."}}, "patternProperties": {}}
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert "patternProperties" in str(excinfo.value)

    def test_defs_block_is_rejected_with_guidance(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {"step": {"$ref": "#/$defs/Step", "description": "The step."}},
                "$defs": {"Step": {"type": "object", "properties": {}}},
            }
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert "$defs" in str(excinfo.value)

    def test_ref_to_an_unknown_definition_is_rejected(self):
        raw = json.dumps(
            {"type": "object", "properties": {"step": {"$ref": "#/$defs/Ghost", "description": "The step."}}}
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names={"Step"})

        assert "Ghost" in str(excinfo.value)

    def test_ref_with_no_saved_definitions_is_rejected(self):
        raw = json.dumps(
            {"type": "object", "properties": {"step": {"$ref": "#/$defs/Step", "description": "The step."}}}
        )

        with pytest.raises(StructuredOutputError):
            parse_json_schema(raw, existing_names=set())

    def test_required_listing_an_unknown_property_is_rejected(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {"answer": {"type": "string", "description": "The answer."}},
                "required": ["missing"],
            }
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert "missing" in str(excinfo.value)

    def test_field_name_that_is_not_an_identifier_is_rejected(self):
        raw = json.dumps(
            {"type": "object", "properties": {"bad name": {"type": "string", "description": "A."}}}
        )

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert "bad name" in str(excinfo.value)

    def test_field_without_a_description_is_rejected(self):
        raw = json.dumps({"type": "object", "properties": {"answer": {"type": "string"}}})

        with pytest.raises(StructuredOutputError) as excinfo:
            parse_json_schema(raw, existing_names=set())

        assert "answer" in str(excinfo.value)

    def test_duplicate_field_names_are_rejected(self):
        raw = json.dumps(
            {
                "type": "object",
                "properties": {
                    "Answer": {"type": "string", "description": "A."},
                    "answer": {"type": "string", "description": "B."},
                },
            }
        )

        with pytest.raises(StructuredOutputError):
            parse_json_schema(raw, existing_names=set())


class TestParseRoundTrip:
    def test_compiling_parsed_fields_reproduces_the_shape(self):
        raw = json.dumps(
            {
                "title": "MathReasoning",
                "description": "Reasoning steps, then the answer.",
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/Step"},
                        "description": "Ordered steps.",
                    },
                    "answer": {"type": "string", "description": "The answer."},
                },
                "required": ["steps", "answer"],
            }
        )
        step = definition(name="Step", description="A step.", fields=[field("text", "string", "The step.")])

        parsed = parse_json_schema(raw, existing_names={"Step"})
        compiled = compile_schema(
            Definition(name="MathReasoning", description=parsed.description, fields=parsed.fields),
            {"Step": step},
        )

        assert compiled["title"] == "MathReasoning"
        assert compiled["properties"]["steps"]["items"] == {"$ref": "#/$defs/Step"}
        assert compiled["properties"]["answer"]["type"] == "string"
        assert compiled["required"] == ["steps", "answer"]
        assert set(compiled["$defs"]) == {"Step"}
