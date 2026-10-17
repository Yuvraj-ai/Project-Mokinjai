"""User-defined tools: the kernel's tool path, the injected ctx, and execute_tool.

`ctx` is offline by construction, and that is the resolution of the contradiction
between the tool design's "ctx: database, HTTP, knowledge base access" and ADR-010's
`--network none`. These tests pin the surface that exists and pin the absence of the one
that cannot.

**`ctx` is never a parameter.** It is bound as a name in the execution namespace, so
every fixture below *uses* `ctx` in the body without declaring it (tools spec §7). A
fixture written as `def add(ctx, a: int)` would be wrong twice over: the extractor would
report a `ctx` parameter the LLM should never see, and `execute_tool` would receive an
argument the caller cannot supply.
"""

import pytest

from app.services.sandbox.backends import SandboxConfig
from app.services.sandbox.errors import ErrorKind
from app.services.sandbox.session import SandboxSession
from app.services.sandbox.tools import InMemoryToolSource

ADD = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''

EXTRACT = '''
def extract(name: str) -> dict:
    """Write a file and report what the context can see."""
    path = ctx.write_output("extracted.txt", "pulled out")
    return {"path": path, "inputs": sorted(ctx.list_inputs())}
'''

LOUD = '''
def loud(message: str) -> str:
    """Print and return."""
    print("working")
    return message.upper()
'''

BROKEN = '''
def explode() -> None:
    """Raise."""
    raise RuntimeError("tool failed")
'''

NOT_JSON = '''
def opaque() -> object:
    """Return something that cannot cross the wire."""
    return object()
'''

PEEKING = '''
def peeking() -> str:
    """Try to climb out of the sandbox directory."""
    return ctx.read_input("../../etc/passwd")
'''

PROBE = '''
def probe() -> dict:
    """Report what the context does and does not have."""
    return {
        "has_database": hasattr(ctx, "database"),
        "has_http": hasattr(ctx, "http"),
        "has_knowledge_base": hasattr(ctx, "knowledge_base"),
        "has_read_input": hasattr(ctx, "read_input"),
    }
'''

READ_NOTE = '''
def read_note() -> str:
    """Read a mounted file."""
    return ctx.read_input("one.txt").decode("utf-8")
'''

SCRATCH = '''
def scratch() -> str:
    """Use work_file and log."""
    ctx.log("logging from tool")
    path = ctx.work_file("scratch.txt")
    with open(path, "w") as f:
        f.write("saved")
    return open(path).read()
'''

SET_LEAK = '''
def set_leak() -> int:
    global leaked_var
    leaked_var = 99
    return leaked_var
'''

GET_LEAK = '''
def get_leak() -> int:
    return leaked_var
'''


def make_session(tmp_path, sources):
    (tmp_path / "documents").mkdir(exist_ok=True)
    (tmp_path / "documents" / "one.txt").write_text("first")
    (tmp_path / "documents" / "two.txt").write_text("second")

    return SandboxSession(
        config=SandboxConfig(backend="subprocess", timeout_seconds=10),
        data_dir=str(tmp_path / "documents"),
        tools=InMemoryToolSource(sources),
        run_id="tool-tests",
    )


@pytest.fixture
def session(tmp_path):
    built = make_session(
        tmp_path,
        {
            "add": ADD,
            "extract": EXTRACT,
            "loud": LOUD,
            "explode": BROKEN,
            "opaque": NOT_JSON,
            "peeking": PEEKING,
            "probe": PROBE,
            "read_note": READ_NOTE,
            "scratch": SCRATCH,
            "set_leak": SET_LEAK,
            "get_leak": GET_LEAK,
        },
    )
    yield built
    built.close()


class TestExecuteTool:
    def test_a_tool_runs_with_ctx_and_returns_its_value(self, session):
        result = session.execute_tool("add", {"a": 2, "b": 40})

        assert result.error is None
        assert result.result == 42

    def test_the_tool_s_stdout_is_captured_separately_from_its_result(self, session):
        result = session.execute_tool("loud", {"message": "hello"})

        assert result.stdout == "working\n"
        assert result.result == "HELLO"

    def test_a_tool_that_raises_is_a_code_error(self, session):
        result = session.execute_tool("explode")

        assert result.error.kind == ErrorKind.CODE_ERROR.value
        assert "tool failed" in result.error.message

    def test_a_result_that_cannot_cross_the_wire_is_a_code_error_naming_the_type(self, session):
        result = session.execute_tool("opaque")

        assert result.error.kind == ErrorKind.CODE_ERROR.value
        assert "object" in result.error.message
        assert "JSON" in result.error.message

    def test_an_unknown_tool_is_tool_not_found(self, session):
        result = session.execute_tool("missing")

        assert result.error.kind == ErrorKind.TOOL_NOT_FOUND.value
        assert "missing" in result.error.message

    def test_ctx_cannot_be_supplied_by_the_caller(self, session):
        result = session.execute_tool("add", {"ctx": "mine", "a": 1, "b": 2})

        assert result.error.kind == ErrorKind.INVALID_ARGS.value

    def test_arguments_that_cannot_cross_the_wire_are_invalid_args(self, session):
        result = session.execute_tool("add", {"a": object(), "b": 2})

        assert result.error.kind == ErrorKind.INVALID_ARGS.value

    def test_a_session_with_no_tool_source_reports_tool_not_found(self, tmp_path):
        session = SandboxSession(config=SandboxConfig(backend="subprocess"))
        try:
            result = session.execute_tool("add", {"a": 1, "b": 2})
        finally:
            session.close()

        assert result.error.kind == ErrorKind.TOOL_NOT_FOUND.value

    def test_non_mapping_args_is_invalid_args(self, session):
        result = session.execute_tool("add", "not-a-dict")

        assert result.error.kind == ErrorKind.INVALID_ARGS.value
        assert "mapping" in result.error.message

    def test_namespace_isolation_between_tool_calls(self, session):
        first = session.execute_tool("set_leak")
        assert first.result == 99

        second = session.execute_tool("get_leak")
        assert second.error.kind == ErrorKind.CODE_ERROR.value
        assert "leaked_var" in second.error.detail


class TestTheOfflineContext:
    def test_ctx_lists_the_mounted_knowledge_base_files(self, session):
        result = session.execute_tool("extract", {"name": "unused"})

        assert result.error is None
        assert result.result["inputs"] == ["one.txt", "two.txt"]

    def test_ctx_writes_into_the_output_directory_the_caller_collects(self, session):
        result = session.execute_tool("extract", {"name": "unused"})

        assert result.result["path"].endswith("extracted.txt")
        assert [(f.name, f.data) for f in result.generated_files] == [
            ("extracted.txt", b"pulled out")
        ]

    def test_ctx_refuses_a_path_that_escapes_the_sandbox(self, session):
        result = session.execute_tool("peeking")

        assert result.error.kind == ErrorKind.CODE_ERROR.value
        assert "escapes" in result.error.message

    def test_ctx_offers_no_database_network_or_object_storage(self, session):
        """The resolution of the ctx-versus-`--network none` contradiction, asserted.

        The tool design promised a ctx with database, HTTP and knowledge-base access.
        ADR-010 runs the container with `--network none` and gives it no database and no
        object-storage credential, so that surface cannot exist. What exists is what the
        container can reach — and the absence is deliberate, because a capability that
        is not there cannot be used by mistake.
        """
        result = session.execute_tool("probe")

        assert result.result == {
            "has_database": False,
            "has_http": False,
            "has_knowledge_base": False,
            "has_read_input": True,
        }

    def test_ctx_reads_mounted_file_contents(self, session):
        result = session.execute_tool("read_note")

        assert result.error is None
        assert result.result == "first"

    def test_ctx_work_file_and_log(self, session):
        result = session.execute_tool("scratch")

        assert result.error is None
        assert result.stdout == "logging from tool\n"
        assert result.result == "saved"

    def test_a_source_that_does_not_know_the_name_is_tool_not_found(self, tmp_path):
        source = make_session(tmp_path, {"typo": "def typo(a: int) -> int:\n    return a\n"})
        try:
            result = source.execute_tool("add", {"a": 1})
        finally:
            source.close()

        assert result.error.kind == ErrorKind.TOOL_NOT_FOUND.value

    def test_the_source_must_define_the_named_function(self, tmp_path):
        session = make_session(tmp_path, {"mismatch": "def something_else():\n    return 1\n"})
        try:
            result = session.execute_tool("mismatch")
        finally:
            session.close()

        assert result.error.kind == ErrorKind.CODE_ERROR.value
        assert "does not define a function of that name" in result.error.message


class TestToolSourceIsAProtocol:
    def test_a_plain_object_with_the_one_method_is_a_tool_source(self):
        from app.services.sandbox.tools import ToolSource

        class Mine:
            def source_for(self, name):
                return None

        assert isinstance(Mine(), ToolSource)

    def test_the_in_memory_source_returns_source_and_nothing_for_a_miss(self):
        source = InMemoryToolSource({"a": "def a(): pass"})

        assert source.source_for("a") == "def a(): pass"
        assert source.source_for("b") is None
