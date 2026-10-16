"""Extracting a tool schema from user-written Python.

The rules are the feature: a docstring summary becomes the description, `Args:`
entries become parameter descriptions, type hints become JSON Schema types, and the
return annotation becomes the output type. Nothing here touches a database —
`extract_schema` takes a string.
"""

import pytest

from app.services.tool_schema import compile_input_schema, extract_schema


WEATHER = '''
def get_weather(city: str, units: str = "metric") -> str:
    """Report the weather for a city.

    Args:
        city: The city to report on, e.g. Lisbon.
        units: Either "metric" or "imperial".
    """
    return f"{city}: 18 degrees ({units})"
'''


class TestExtraction:
    def test_a_tool_extracts_its_name_description_parameters_and_return(self):
        result = extract_schema(WEATHER)

        assert result.errors == []
        assert result.schema is not None
        assert result.schema.name == "get_weather"
        assert result.schema.description == "Report the weather for a city."
        assert [parameter.name for parameter in result.schema.parameters] == ["city", "units"]
        assert result.schema.parameters[0].description == "The city to report on, e.g. Lisbon."
        assert result.schema.parameters[0].type == "string"
        assert result.schema.returns == "string"

    def test_parameters_keep_their_declared_order(self):
        result = extract_schema(
            '''
def reorder(second: int, first: int) -> int:
    """Swap two numbers.

    Args:
        second: The value listed first but named second.
        first: The value listed second but named first.
    """
    return second - first
'''
        )

        assert [parameter.name for parameter in result.schema.parameters] == ["second", "first"]

    def test_the_description_stops_at_the_args_section_with_no_blank_line(self):
        result = extract_schema(
            '''
def tidy(city: str) -> str:
    """Report the weather for a city.
    Args:
        city: The city to report on.
    """
    return city
'''
        )

        assert result.schema.description == "Report the weather for a city."

    def test_a_wrapped_args_entry_keeps_its_continuation(self):
        result = extract_schema(
            '''
def long_hand(city: str) -> str:
    """Report the weather.

    Args:
        city: The city to report on, which may be given with a country
            suffix, e.g. Lisbon, PT.
    """
    return city
'''
        )

        assert (
            result.schema.parameters[0].description
            == "The city to report on, which may be given with a country suffix, e.g. Lisbon, PT."
        )

    def test_a_type_written_in_parentheses_in_args_is_ignored(self):
        """The type hint is the single source of truth; the prose cannot override it."""
        result = extract_schema(
            '''
def typed(city: int) -> str:
    """Report the weather.

    Args:
        city (str): The city, declared `int` in the signature on purpose.
    """
    return str(city)
'''
        )

        assert result.errors == []
        assert result.schema.parameters[0].type == "integer"


class TestTypes:
    @pytest.mark.parametrize(
        "annotation,expected",
        [
            ("str", "string"),
            ("int", "integer"),
            ("float", "number"),
            ("bool", "boolean"),
            ("list", "array"),
            ("dict", "object"),
        ],
    )
    def test_each_supported_annotation_maps_to_its_schema_type(self, annotation, expected):
        source = f'''
def typed(value: {annotation}) -> str:
    """Describe a value.

    Args:
        value: The value to describe.
    """
    return str(value)
'''
        result = extract_schema(source)

        assert result.errors == [], result.errors
        assert result.schema.parameters[0].type == expected

    def test_a_list_parameter_carries_its_item_type(self):
        result = extract_schema(
            '''
def typed(values: list[str]) -> str:
    """Describe values.

    Args:
        values: The values to describe.
    """
    return str(values)
'''
        )

        assert result.schema.parameters[0].type == "array"
        assert result.schema.parameters[0].items_type == "string"

    def test_a_bare_list_has_unconstrained_items(self):
        result = extract_schema(
            '''
def typed(values: list) -> str:
    """Describe values.

    Args:
        values: The values to describe.
    """
    return str(values)
'''
        )

        assert result.schema.parameters[0].type == "array"
        assert result.schema.parameters[0].items_type is None

    def test_a_parameter_with_a_default_is_not_required(self):
        result = extract_schema(WEATHER)

        by_name = {parameter.name: parameter for parameter in result.schema.parameters}
        assert by_name["city"].required is True
        assert by_name["units"].required is False

    @pytest.mark.parametrize("annotation", ["Optional[str]", "str | None", "typing.Optional[str]"])
    def test_an_annotation_that_admits_none_is_not_required(self, annotation):
        source = f'''
def typed(value: {annotation}) -> str:
    """Describe a value.

    Args:
        value: The value to describe.
    """
    return str(value)
'''
        result = extract_schema(source)

        assert result.errors == [], result.errors
        assert result.schema.parameters[0].type == "string"
        assert result.schema.parameters[0].required is False

    @pytest.mark.parametrize(
        "annotation,expected",
        [("str", "string"), ("int", "integer"), ("float", "number"), ("bool", "boolean"), ("None", "null")],
    )
    def test_the_return_annotation_maps_to_the_output_type(self, annotation, expected):
        source = f'''
def typed(value: str) -> {annotation}:
    """Describe a value.

    Args:
        value: The value to describe.
    """
    return value
'''
        result = extract_schema(source)

        assert result.errors == [], result.errors
        assert result.schema.returns == expected


class TestCompiledSchema:
    def test_the_input_schema_is_an_object_with_no_additional_properties(self):
        schema = extract_schema(WEATHER).schema

        compiled = compile_input_schema(schema)

        assert compiled["type"] == "object"
        assert compiled["additionalProperties"] is False
        assert set(compiled["properties"]) == {"city", "units"}

    def test_every_parameter_carries_its_description_and_type(self):
        schema = extract_schema(WEATHER).schema

        compiled = compile_input_schema(schema)

        assert compiled["properties"]["city"] == {
            "type": "string",
            "description": "The city to report on, e.g. Lisbon.",
        }

    def test_required_lists_only_the_required_parameters(self):
        schema = extract_schema(WEATHER).schema

        assert compile_input_schema(schema)["required"] == ["city"]

    def test_an_array_parameter_compiles_its_item_type(self):
        schema = extract_schema(
            '''
def typed(values: list[str]) -> str:
    """Describe values.

    Args:
        values: The values to describe.
    """
    return str(values)
'''
        ).schema

        assert compile_input_schema(schema)["properties"]["values"]["items"] == {"type": "string"}


class TestRejections:
    @pytest.mark.parametrize(
        "source,expected",
        [
            ("def broken( -> str:", "does not parse"),
            ("VALUE = 1\n", "exactly one top-level function"),
            (
                "def one() -> str:\n    return ''\n\n\ndef two() -> str:\n    return ''\n",
                "defines 2",
            ),
            (
                'async def slow() -> str:\n    """Do a thing.\n\n    Args:\n        none: nothing.\n    """\n',
                "async",
            ),
            ("def bare() -> str:\n    return ''\n", "no docstring"),
            ('def bare() -> str:\n    """"""\n    return \'\'\n', "no docstring"),
            (
                'def bare() -> str:\n    """Do a thing."""\n    return ""\n',
                "no `Args:` section",
            ),
            (
                'def one(value: str) -> str:\n    """Do a thing.\n\n    Args:\n        other: Not a parameter.\n    """\n    return value\n',
                "not parameters",
            ),
            (
                'def one(value, other: str) -> str:\n    """Do a thing.\n\n    Args:\n        value: The value.\n        other: The other value.\n    """\n    return value\n',
                "type hint",
            ),
            (
                'def one(value: str):\n    """Do a thing.\n\n    Args:\n        value: The value.\n    """\n    return value\n',
                "no return annotation",
            ),
            (
                'def one(value: pandas.DataFrame) -> str:\n    """Do a thing.\n\n    Args:\n        value: The value.\n    """\n    return value\n',
                "cannot be described",
            ),
            (
                'def one(value: str) -> pandas.DataFrame:\n    """Do a thing.\n\n    Args:\n        value: The value.\n    """\n    return value\n',
                "cannot be described",
            ),
            (
                'def one(*values: str) -> str:\n    """Do a thing.\n\n    Args:\n        values: The values.\n    """\n    return values\n',
                "*values",
            ),
        ],
    )
    def test_each_rejection_names_what_is_missing(self, source, expected):
        result = extract_schema(source)

        assert result.schema is None
        assert any(expected in error for error in result.errors), result.errors

    def test_a_syntax_error_reports_the_line(self):
        result = extract_schema('def broken( -> str:')

        assert result.schema is None
        assert "line 1" in result.errors[0]

    def test_an_unsupported_annotation_lists_what_is_supported(self):
        result = extract_schema(
            '''
def one(value: pandas.DataFrame) -> str:
    """Do a thing.

    Args:
        value: The value.
    """
    return value
'''
        )

        assert "pandas.DataFrame" in result.errors[0]
        assert "Optional" in result.errors[0]

    def test_every_unannotated_parameter_is_named_in_one_message(self):
        """One message, not one per parameter: the editor shows them together."""
        result = extract_schema(
            '''
def one(first, second, third: int) -> str:
    """Do a thing.

    Args:
        first: The first.
        second: The second.
        third: The third.
    """
    return str(third)
'''
        )

        assert len(result.errors) == 1
        assert "first" in result.errors[0]
        assert "second" in result.errors[0]
        assert "third" not in result.errors[0]

    def test_a_docstring_that_starts_blank_is_rejected(self):
        result = extract_schema(
            '''
def one(value: str) -> str:
    """
    Args:
        value: The value.
    """
    return value
'''
        )

        assert result.schema is None
        assert "nothing to use as the tool description" in result.errors[0]
