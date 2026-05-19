import json
from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext


class TransformModule(BaseModule):
    """Transform module - transforms data between formats."""

    module_type = "transform"

    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        input_value = inputs.get("input", "")
        transformation = config.get("transformation", "passthrough")

        if transformation == "json_parse":
            if isinstance(input_value, str):
                output = json.loads(input_value)
            else:
                output = input_value
        elif transformation == "json_stringify":
            output = json.dumps(input_value, indent=2)
        elif transformation == "extract_field":
            field = config.get("field", "")
            if isinstance(input_value, dict):
                output = input_value.get(field, None)
            elif isinstance(input_value, str):
                try:
                    parsed = json.loads(input_value)
                    output = parsed.get(field, None)
                except json.JSONDecodeError:
                    output = input_value
            else:
                output = input_value
        elif transformation == "uppercase":
            output = str(input_value).upper()
        elif transformation == "lowercase":
            output = str(input_value).lower()
        elif transformation == "trim":
            output = str(input_value).strip()
        elif transformation == "split":
            delimiter = config.get("delimiter", "\n")
            output = str(input_value).split(delimiter)
        elif transformation == "join":
            delimiter = config.get("delimiter", "\n")
            if isinstance(input_value, list):
                output = delimiter.join(str(item) for item in input_value)
            else:
                output = str(input_value)
        else:
            # passthrough
            output = input_value

        return {"output": output}
