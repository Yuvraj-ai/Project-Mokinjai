from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.modules.input import InputModule
from app.engine.modules.agent import AgentModule
from app.engine.modules.prompt import PromptModule
from app.engine.modules.output import OutputModule
from app.engine.modules.conditional import ConditionalModule
from app.engine.modules.transform import TransformModule
from app.engine.modules.http_request import HttpRequestModule

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
    
    _instances: dict[str, BaseModule] = {}

    @classmethod
    def get_module(cls, node_type: str) -> BaseModule:
        if node_type not in cls._instances:
            module_class = cls._modules.get(node_type)
            if module_class is None:
                raise ValueError(f"Unknown module type: {node_type}")
            cls._instances[node_type] = module_class()
        return cls._instances[node_type]

    @classmethod
    def register(cls, node_type: str, module_class: type[BaseModule]):
        cls._modules[node_type] = module_class
        if node_type in cls._instances:
            del cls._instances[node_type]

    @classmethod
    def list_types(cls) -> list[str]:
        return list(cls._modules.keys())
