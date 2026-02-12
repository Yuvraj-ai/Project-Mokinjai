import re
from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext


class PromptModule(BaseModule):
    """Prompt template module - formats prompts with variables."""

    module_type = "prompt"

    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        template = config.get("template", "")

        # Build variable map from inputs
        variables = {}

        # Flatten inputs from parent nodes
        for key, value in inputs.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    variables[k] = str(v) if not isinstance(v, str) else v
            else:
                variables[key] = str(value) if not isinstance(value, str) else value

        # Also include any explicitly defined variables in config
        config_vars = config.get("variables", {})
        if isinstance(config_vars, dict):
            variables.update(config_vars)

        # Replace {{variable}} placeholders
        def replace_var(match):
            var_name = match.group(1).strip()
            return variables.get(var_name, match.group(0))

        prompt = re.sub(r"\{\{(.+?)\}\}", replace_var, template)

        return {"output": prompt, "prompt": prompt}
