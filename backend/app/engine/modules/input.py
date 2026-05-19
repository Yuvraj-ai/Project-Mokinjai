from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext


class InputModule(BaseModule):
    """Input module - passes through the workflow's initial input or node's default value."""

    module_type = "input"

    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        # Get input from upstream nodes
        upstream_input = inputs.get("input")

        # Determine the value to use:
        # 1. If upstream input is a non-empty string, use it
        # 2. Otherwise, use the node's default value from config
        if isinstance(upstream_input, str) and upstream_input.strip():
            value = upstream_input
        else:
            value = config.get("value", "")

        return {"output": value, "input": value}