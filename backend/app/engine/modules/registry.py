from typing import Any
from app.logging import logger
from app.engine.modules.base import BaseModule
from app.engine.modules.agent import AgentModule
from app.engine.modules.prompt import PromptModule
from app.engine.modules.output import OutputModule
from app.engine.modules.conditional import ConditionalModule
from app.engine.modules.transform import TransformModule
from app.engine.modules.http_request import HttpRequestModule


class InputModule(BaseModule):
    """Input module - passes through the workflow's initial input."""

    module_type = "input"

    async def execute(self, config, inputs, context):
        return {"output": inputs.get("input", context.input_data)}


class ModuleRegistry:
    """Registry mapping node types to their module implementations."""

    _modules: dict[str, type[BaseModule]] = {
        "input": InputModule,
        "agent": AgentModule,
        "prompt": PromptModule,
        "output": OutputModule,
        "conditional": ConditionalModule,
        "transform": TransformModule,
        "http_request": HttpRequestModule,
    }

    @classmethod
    def get_module(cls, node_type: str) -> BaseModule:
        module_class = cls._modules.get(node_type)
        if module_class is None:
            logger.error(f"Unknown module type requested: {node_type}")
            raise ValueError(f"Unknown module type: {node_type}")
        return module_class()

    @classmethod
    def register(cls, node_type: str, module_class: type[BaseModule]):
        cls._modules[node_type] = module_class
        logger.info(f"Module registered: {node_type}")

    @classmethod
    def list_types(cls) -> list[str]:
        return list(cls._modules.keys())
