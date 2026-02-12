import re
from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext


class ConditionalModule(BaseModule):
    """Conditional module - branches execution based on conditions."""

    module_type = "conditional"

    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        input_value = inputs.get("input", "")
        if isinstance(input_value, dict):
            input_value = str(input_value)

        condition_type = config.get("conditionType", "contains")
        condition_value = config.get("conditionValue", "")

        result = self._evaluate(input_value, condition_type, condition_value)

        return {
            "output": input_value,
            "branch": "true" if result else "false",
            "condition_result": result,
        }

    def _evaluate(self, input_value: str, condition_type: str, condition_value: str) -> bool:
        input_str = str(input_value)

        if condition_type == "contains":
            return condition_value.lower() in input_str.lower()
        elif condition_type == "equals":
            return input_str.strip() == condition_value.strip()
        elif condition_type == "not_equals":
            return input_str.strip() != condition_value.strip()
        elif condition_type == "regex":
            return bool(re.search(condition_value, input_str))
        elif condition_type == "greater_than":
            try:
                return float(input_str) > float(condition_value)
            except ValueError:
                return False
        elif condition_type == "less_than":
            try:
                return float(input_str) < float(condition_value)
            except ValueError:
                return False
        else:
            return bool(input_value)
