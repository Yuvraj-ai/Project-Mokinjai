import pytest
from app.engine.context import ExecutionContext


class TestExecutionContext:
    def test_init_with_input_data(self):
        ctx = ExecutionContext({"key": "value"})
        assert ctx.input_data == {"key": "value"}

    def test_init_without_input_data(self):
        ctx = ExecutionContext()
        assert ctx.input_data == {}

    def test_set_and_get_output(self):
        ctx = ExecutionContext()
        ctx.set_output("node_1", {"output": "hello"})
        assert ctx.get_output("node_1") == {"output": "hello"}

    def test_get_output_nonexistent(self):
        ctx = ExecutionContext()
        assert ctx.get_output("nonexistent") is None

    def test_get_inputs_for_no_parents(self):
        ctx = ExecutionContext({"message": "hello"})
        inputs = ctx.get_inputs_for("node_1", [])
        assert inputs == {"input": {"message": "hello"}}

    def test_get_inputs_for_with_parents(self):
        ctx = ExecutionContext()
        ctx.set_output("parent_1", {"output": "result"})
        inputs = ctx.get_inputs_for("child_1", ["parent_1"])
        assert inputs["parent_1"] == {"output": "result"}
        assert inputs["input"] == "result"

    def test_get_inputs_flattens_response_key(self):
        ctx = ExecutionContext()
        ctx.set_output("parent_1", {"response": "ai response"})
        inputs = ctx.get_inputs_for("child_1", ["parent_1"])
        assert inputs["input"] == "ai response"

    def test_add_trace_entry(self):
        ctx = ExecutionContext()
        ctx.add_trace_entry("node_1", "prompt", "completed", inputs={"a": 1}, outputs={"b": 2})
        assert len(ctx.trace) == 1
        assert ctx.trace[0]["node_id"] == "node_1"
        assert ctx.trace[0]["status"] == "completed"

    def test_add_token_usage(self):
        ctx = ExecutionContext()
        ctx.add_token_usage({"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})
        assert ctx.total_token_usage["prompt_tokens"] == 10
        ctx.add_token_usage({"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10})
        assert ctx.total_token_usage["prompt_tokens"] == 15
        assert ctx.total_token_usage["total_tokens"] == 40

    def test_skip_node(self):
        ctx = ExecutionContext()
        ctx.skip_node("node_1")
        assert ctx.is_skipped("node_1") is True
        assert ctx.is_skipped("node_2") is False

    def test_get_final_output_empty(self):
        ctx = ExecutionContext()
        assert ctx.get_final_output() == {}

    def test_get_final_output(self):
        ctx = ExecutionContext()
        ctx.set_output("node_1", {"output": "first"})
        ctx.set_output("node_2", {"output": "last"})
        assert ctx.get_final_output() == {"output": "last"}
