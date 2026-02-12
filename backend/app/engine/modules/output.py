from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext


class OutputModule(BaseModule):
    """Output module - collects and formats the final output."""

    module_type = "output"

    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        # Collect input from upstream
        output_value = inputs.get("input", "")

        output_format = config.get("format", "text")

        if output_format == "json" and isinstance(output_value, str):
            import json
            try:
                output_value = json.loads(output_value)
            except json.JSONDecodeError:
                pass

        return {"output": output_value}
