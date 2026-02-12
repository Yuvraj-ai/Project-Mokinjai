from abc import ABC, abstractmethod
from typing import Any
from app.engine.context import ExecutionContext


class BaseModule(ABC):
    """Abstract base class for all workflow modules."""

    module_type: str = "base"

    @abstractmethod
    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        """Execute the module and return output data."""
        ...

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate module configuration. Override in subclasses."""
        return True
