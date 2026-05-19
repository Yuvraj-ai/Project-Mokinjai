from datetime import datetime, timezone
from typing import Any


class ExecutionContext:
    """Manages execution state: node outputs, execution trace, and token usage."""

    def __init__(self, input_data: dict[str, Any] | None = None):
        self.input_data = input_data or {}
        self.node_outputs: dict[str, dict[str, Any]] = {}
        self.trace: list[dict] = []
        self.total_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.skipped_nodes: set[str] = set()

    def set_output(self, node_id: str, data: dict[str, Any]):
        self.node_outputs[node_id] = data

    def get_output(self, node_id: str) -> dict[str, Any] | None:
        return self.node_outputs.get(node_id)

    def get_inputs_for(self, node_id: str, parent_ids: list[str]) -> dict[str, Any]:
        """Collect outputs from all parent nodes as input for this node."""
        inputs = {}

        # Include global input data
        if not parent_ids:
            inputs["input"] = self.input_data

        for parent_id in parent_ids:
            parent_output = self.get_output(parent_id)
            if parent_output:
                # Merge parent outputs - later parents override earlier ones
                inputs[parent_id] = parent_output
                # Also provide a flat "input" key with the main output value
                if "output" in parent_output:
                    inputs["input"] = parent_output["output"]
                elif "response" in parent_output:
                    inputs["input"] = parent_output["response"]

        return inputs

    def add_trace_entry(
        self,
        node_id: str,
        node_type: str,
        status: str,
        inputs: dict | None = None,
        outputs: dict | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ):
        self.trace.append({
            "node_id": node_id,
            "node_type": node_type,
            "status": status,
            "inputs": inputs,
            "outputs": outputs,
            "error": error,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def add_token_usage(self, usage: dict):
        for key in self.total_token_usage:
            self.total_token_usage[key] += usage.get(key, 0)

    def skip_node(self, node_id: str):
        self.skipped_nodes.add(node_id)

    def is_skipped(self, node_id: str) -> bool:
        return node_id in self.skipped_nodes

    def get_final_output(self) -> dict[str, Any]:
        """Return the output of the last executed node."""
        if not self.node_outputs:
            return {}
        # Return the last node's output
        last_key = list(self.node_outputs.keys())[-1]
        return self.node_outputs[last_key]
