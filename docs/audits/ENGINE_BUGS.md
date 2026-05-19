# Engine Bug Report — `backend/app/engine`

> **Purpose:** This file is intended to be read by an AI CLI agent.
> Each issue is described with its exact file, line range, root cause, and a concrete fix.
> Fix each issue in the order listed. Do NOT skip any issue.

---

## ISSUE 1 — `executor.py`: Missing blank line between import groups (cosmetic but PEP8-breaking)

**File:** `backend/app/engine/executor.py`
**Lines:** 1–12

**Problem:**
There is no blank line separating the stdlib/third-party imports from the local imports. Additionally, the `BlobService` import is separated from the other local imports by a blank line, which breaks import grouping conventions.

```python
# Current (broken grouping):
import time
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.workflow import Workflow
from app.models.execution import Execution
from app.engine.dag_builder import DAGBuilder
from app.engine.context import ExecutionContext
from app.engine.modules.registry import ModuleRegistry


from app.services.blob_service import BlobService   # <-- orphaned
```

**Fix:** Merge `BlobService` with the other local imports and add a blank line between stdlib/third-party and local groups:

```python
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.context import ExecutionContext
from app.engine.dag_builder import DAGBuilder
from app.engine.modules.registry import ModuleRegistry
from app.models.execution import Execution
from app.models.workflow import Workflow
from app.services.blob_service import BlobService
```

---

## ISSUE 2 — `executor.py`: `start_time` is referenced in `except` block but is only assigned inside `try`

**File:** `backend/app/engine/executor.py`
**Lines:** 45, 113

**Problem:**
`start_time = time.time()` is set at line 45 *before* the `try` block but *after* the early-exit guard for a missing workflow. If the flow definition fetch (`BlobService.get_blob`) raises an exception that isn't `ValueError`, the `except` block at line 113 still tries to compute `total_time = int((time.time() - start_time) * 1000)`. This is fine in the current layout because `start_time` is indeed before the try, but the *real* bug is that `start_time` is placed between two separate `try` paths — the workflow-not-found early return and the main execution try — making it hard to reason about. More critically, if any exception is raised *before* `start_time` is assigned (e.g. on line 45 if execution.started_at throws), `start_time` would be undefined in the except.

**Fix:** Move `start_time` to *before* setting `execution.status = "running"` so it is always assigned before any try block:

```python
# Load workflow ...
# (early return guards above)

start_time = time.time()   # Move here — before any try block

# Start execution
execution.status = "running"
execution.started_at = datetime.now(timezone.utc)
await self.db.commit()

try:
    ...
except Exception as e:
    total_time = int((time.time() - start_time) * 1000)
    ...
```

---

## ISSUE 3 — `executor.py`: `add_trace_entry` called with wrong positional argument order for skipped nodes

**File:** `backend/app/engine/executor.py`
**Line:** 61

**Problem:**
`context.add_trace_entry(node_id, "skipped", "skipped")` passes `"skipped"` as **both** `node_type` and `status`. The actual node type is available at that point from `dag.nodes[node_id]["type"]` (the node dict is accessed on line 64 just after this call). This means every skipped node's trace entry will show `node_type = "skipped"` instead of the real type, making traces misleading.

**Fix:**
```python
# Before the continue:
if context.is_skipped(node_id):
    node = dag.nodes[node_id]
    context.add_trace_entry(node_id, node["type"], "skipped")
    continue
```

---

## ISSUE 4 — `executor.py`: Bare `'context' in locals()` check is fragile and incorrect

**File:** `backend/app/engine/executor.py`
**Lines:** 117–119

**Problem:**
```python
if 'context' in locals():
    trace_data = {"nodes": context.trace}
    execution.mongo_trace_id = await BlobService.save_blob(trace_data)
```
`locals()` inside an `except` block in Python does include variables defined in the enclosing `try` body *only if Python has actually executed those lines*. However, this pattern is fragile, CPython-implementation-specific, and confusing. If the exception is raised early (e.g. `BlobService.get_blob` fails), `context` is never assigned but `dag` might be — the check doesn't account for partial state. Additionally, `execution.token_usage` is never persisted in the failure path.

**Fix:** Use a proper `Optional` variable initialized before the try:

```python
context: ExecutionContext | None = None

try:
    ...
    context = ExecutionContext(execution.input_data)
    ...
except Exception as e:
    total_time = int((time.time() - start_time) * 1000)
    execution.status = "failed"
    execution.error_message = str(e)

    if context is not None:
        trace_data = {"nodes": context.trace}
        execution.mongo_trace_id = await BlobService.save_blob(trace_data)
        execution.token_usage = context.total_token_usage

    execution.execution_time_ms = total_time
    execution.completed_at = datetime.now(timezone.utc)
```

---

## ISSUE 5 — `executor.py`: `token_usage` not saved on failure path

**File:** `backend/app/engine/executor.py`
**Lines:** 112–122

**Problem:**
In the `except` block (failure path), `execution.token_usage` is never set even if some nodes ran successfully before the failure and accumulated token usage in `context`. This means partially-run workflows report zero token usage on failure.

**Fix:** (Covered by Issue 4 fix) — add `execution.token_usage = context.total_token_usage` inside the `if context is not None` block in the except handler.

---

## ISSUE 6 — `executor.py`: No HTTP error raising in `HttpRequestModule` — status codes ≥400 silently succeed

**File:** `backend/app/engine/modules/http_request.py`
**Lines:** 29–46

**Problem:**
The HTTP client makes a request and returns the response regardless of HTTP status code. A `404`, `500`, or `401` response will be returned as a successful `output`, meaning downstream nodes will receive error payloads without any indication that the request failed.

**Fix:** Call `response.raise_for_status()` before parsing the response body:

```python
async with httpx.AsyncClient(timeout=timeout) as client:
    response = await client.request(
        method=method,
        url=url,
        headers=headers,
        json=body if method in ("POST", "PUT", "PATCH") else None,
    )

response.raise_for_status()   # <-- ADD THIS LINE

try:
    response_data = response.json()
except Exception:
    response_data = response.text
```

---

## ISSUE 7 — `executor.py` / `http_request.py`: No URL validation — empty URL causes cryptic `httpx` error

**File:** `backend/app/engine/modules/http_request.py`
**Lines:** 19, 29

**Problem:**
If `config.get("url", "")` returns an empty string (misconfigured node), `httpx` raises a `LocalProtocolError` or `InvalidURL` with a confusing message. There is no pre-validation of the URL before making the request.

**Fix:** Add an explicit guard:

```python
url = config.get("url", "").strip()
if not url:
    raise ValueError("HttpRequestModule: 'url' config is required but was not provided.")
```

---

## ISSUE 8 — `dag_builder.py`: `detect_cycles()` uses recursive DFS — will hit Python's recursion limit on large graphs

**File:** `backend/app/engine/dag_builder.py`
**Lines:** 26–47

**Problem:**
The `detect_cycles` method uses recursive DFS with a nested function `dfs(node_id)`. Python's default recursion limit is 1000. For a workflow with a long linear chain of 1000+ nodes this will raise `RecursionError`, which is not caught and will surface as an unhandled 500 error.

Additionally, `detect_cycles()` is called in `validate()` on line 82, and then `topological_sort()` also detects cycles via Kahn's algorithm (if `len(sorted_nodes) != len(self.nodes)`) on line 64. This means cycle detection runs **twice** — the recursive DFS in `validate()` and again implicitly in `topological_sort()`. This is redundant.

**Fix Option A (preferred):** Remove `detect_cycles()` from `validate()` and rely solely on the cycle check in `topological_sort()` (which is already O(V+E) and iterative):

```python
def validate(self):
    """Validate the flow definition."""
    if not self.nodes:
        raise BadRequestException("Workflow has no nodes")

    # Check all edge references exist
    for edge in self.edges:
        if edge["source"] not in self.nodes:
            raise BadRequestException(f"Edge references unknown source node: {edge['source']}")
        if edge["target"] not in self.nodes:
            raise BadRequestException(f"Edge references unknown target node: {edge['target']}")

    # Cycle detection is performed inside topological_sort() via Kahn's algorithm
```

**Fix Option B:** If `detect_cycles()` must be kept, rewrite it iteratively using an explicit stack.

---

## ISSUE 9 — `dag_builder.py`: `_build()` does not guard against duplicate edges

**File:** `backend/app/engine/dag_builder.py`
**Lines:** 18–24

**Problem:**
If `flow_definition["edges"]` contains duplicate edges (same `source` → `target` pair), `_build()` will add the target to `adjacency` twice and increment `in_degree[tgt]` multiple times. This causes:
1. `topological_sort()` to compute wrong in-degree, potentially never reaching `in_degree[neighbor] == 0` for that node.
2. The sorted list to have fewer items than `self.nodes`, triggering a false "cycle detected" error.

**Fix:** Deduplicate edges in `_build()`:

```python
def _build(self):
    seen_edges = set()
    for edge in self.edges:
        src = edge["source"]
        tgt = edge["target"]
        key = (src, tgt)
        if key in seen_edges:
            continue   # skip duplicate edges
        seen_edges.add(key)
        self.adjacency[src].append(tgt)
        self.reverse_adjacency[tgt].append(src)
        self.in_degree[tgt] = self.in_degree.get(tgt, 0) + 1
```

---

## ISSUE 10 — `context.py`: `get_final_output()` returns the last-*inserted* node output, not the last-*executed* node

**File:** `backend/app/engine/context.py`
**Lines:** 73–79

**Problem:**
```python
def get_final_output(self) -> dict[str, Any]:
    last_key = list(self.node_outputs.keys())[-1]
    return self.node_outputs[last_key]
```
`dict` in Python 3.7+ preserves insertion order, so this returns the output of the *last node to call `set_output`*. This is typically correct in a linear DAG. However, in a branching DAG where the conditional skip path causes nodes to be skipped, the last *inserted* key is the last *non-skipped* node in sorted order, which may not be the terminal output node. For example, if the workflow has a structure: `input → conditional → [agent_A, agent_B] → output`, and `agent_A` is skipped, `agent_B` runs before `output`, but `output` is the last inserted key — which is correct. The real risk is if a user has multiple terminal output nodes (no common downstream).

**Bigger bug:** If all nodes are skipped (edge case), `node_outputs` is empty and the method returns `{}` — which is fine. But if the DAG has a dedicated `output` node (type `"output"`), it should always be the source of final output, not merely the last key.

**Fix:** Prefer the output from a node of type `"output"` if one exists in `node_outputs`. Fall back to the last inserted key:

```python
def get_final_output(self) -> dict[str, Any]:
    """Return the output of the designated output node, or last executed node."""
    if not self.node_outputs:
        return {}
    # Prefer a node that was tagged as the final output
    if self._final_output_node_id and self._final_output_node_id in self.node_outputs:
        return self.node_outputs[self._final_output_node_id]
    last_key = list(self.node_outputs.keys())[-1]
    return self.node_outputs[last_key]
```

And add `self._final_output_node_id: str | None = None` to `__init__`, plus a setter:

```python
def mark_as_final_output(self, node_id: str):
    self._final_output_node_id = node_id
```

Then in `executor.py`, when the node type is `"output"`, call `context.mark_as_final_output(node_id)` after `context.set_output(node_id, output)`.

---

## ISSUE 11 — `context.py`: `get_inputs_for` silently drops parent output if parent has no `output` or `response` key

**File:** `backend/app/engine/context.py`
**Lines:** 21–40

**Problem:**
```python
for parent_id in parent_ids:
    parent_output = self.get_output(parent_id)
    if parent_output:
        inputs[parent_id] = parent_output
        if "output" in parent_output:
            inputs["input"] = parent_output["output"]
        elif "response" in parent_output:
            inputs["input"] = parent_output["response"]
```
If a parent module returns a dict that contains neither `"output"` nor `"response"` key (e.g., a custom module returning `{"status_code": 200, "headers": {...}}`), the convenience `inputs["input"]` key is never set. Downstream modules that call `inputs.get("input", "")` will silently receive an empty string instead of the actual parent data.

**Fix:** Fall back to the entire parent output dict when neither key is present:

```python
if "output" in parent_output:
    inputs["input"] = parent_output["output"]
elif "response" in parent_output:
    inputs["input"] = parent_output["response"]
else:
    inputs["input"] = parent_output   # <-- fallback: pass whole dict
```

---

## ISSUE 12 — `agent.py`: Hardcoded outdated model names with a TODO comment left in code

**File:** `backend/app/engine/modules/agent.py`
**Lines:** 5, 19, 96, 138

**Problem:**
Line 5 has `#TODO: FIX THE MODELS THEY ARE OLD`. The defaults are:
- OpenAI: `"gpt-4.1-mini"` (line 19) — this is a hallucinated model name. The correct name is `"gpt-4o-mini"`.
- Anthropic: `"claude-3-haiku-20240307"` (line 96) — this model is deprecated; should be `"claude-3-5-haiku-20241022"` or newer.
- Gemini: `"gemini-2.5-flash"` (line 138) — correct as of mid-2025, but should confirm with settings.

**Fix:**
```python
# agent.py line 19
model = config.get("model", "gpt-4o-mini")   # was "gpt-4.1-mini"

# agent.py line 96
model or "claude-3-5-haiku-20241022"          # was "claude-3-haiku-20240307"

# Remove the TODO comment on line 5
```

---

## ISSUE 13 — `agent.py`: A new `AsyncOpenAI` / `AsyncAnthropic` / `GenerativeModel` client is instantiated on every node execution

**File:** `backend/app/engine/modules/agent.py`
**Lines:** 58, 94, 137

**Problem:**
Each time `AgentModule.execute()` is called, it creates a brand-new HTTP client object (`AsyncOpenAI(...)`, `AsyncAnthropic(...)`, `genai.GenerativeModel(...)`). For the OpenAI and Anthropic clients this also creates a new `httpx.AsyncClient` under the hood per call, wasting TCP connection setup time and memory. This is especially bad in loops or large workflows with many agent nodes.

**Fix:** Use module-level cached clients or a simple class-level cache keyed by API key:

```python
# At module top-level (agent.py):
_openai_clients: dict[str, "AsyncOpenAI"] = {}
_anthropic_clients: dict[str, "AsyncAnthropic"] = {}

def _get_openai_client(api_key: str):
    if api_key not in _openai_clients:
        from openai import AsyncOpenAI
        _openai_clients[api_key] = AsyncOpenAI(api_key=api_key)
    return _openai_clients[api_key]
```

Apply the same pattern for Anthropic. The Gemini `GenerativeModel` is cheap to construct and doesn't hold a connection pool, so it's lower priority.

---

## ISSUE 14 — `agent.py` / `_call_gemini`: `response.usage_metadata` fields may be `None`

**File:** `backend/app/engine/modules/agent.py`
**Lines:** 152–156

**Problem:**
```python
usage = {
    "prompt_tokens": response.usage_metadata.prompt_token_count,
    "completion_tokens": response.usage_metadata.candidates_token_count,
    "total_tokens": response.usage_metadata.total_token_count,
}
```
The Gemini API may return `None` for `usage_metadata` or for individual count fields (e.g. when safety filters block a response or in streaming mode). This will cause an `AttributeError` or `TypeError`.

**Fix:**
```python
metadata = response.usage_metadata or {}
usage = {
    "prompt_tokens": getattr(metadata, "prompt_token_count", 0) or 0,
    "completion_tokens": getattr(metadata, "candidates_token_count", 0) or 0,
    "total_tokens": getattr(metadata, "total_token_count", 0) or 0,
}
```

---

## ISSUE 15 — `agent.py` / `_call_gemini`: `response.text` raises if the response was blocked

**File:** `backend/app/engine/modules/agent.py`
**Line:** 161

**Problem:**
Accessing `response.text` on a Gemini response that was blocked by safety filters raises a `ValueError: The `response.text` quick accessor only works for simple (single-candidate) responses...`. This will cause the entire workflow execution to fail with an opaque error.

**Fix:** Access `response.text` safely:

```python
try:
    text_content = response.text
except (ValueError, AttributeError):
    # Response was blocked or has no text content
    parts = []
    for candidate in (response.candidates or []):
        for part in (candidate.content.parts if candidate.content else []):
            if hasattr(part, "text"):
                parts.append(part.text)
    text_content = "".join(parts) or "[Response blocked by safety filters]"
```

---

## ISSUE 16 — `conditional.py`: `regex` condition type is not guarded against invalid regex patterns

**File:** `backend/app/engine/modules/conditional.py`
**Line:** 43

**Problem:**
```python
elif condition_type == "regex":
    return bool(re.search(condition_value, input_str))
```
If `condition_value` is an invalid regex (e.g. `"[unclosed"`), `re.search` raises `re.error`. This exception propagates up through the executor's node loop and marks the entire workflow as failed, with a cryptic regex error message.

**Fix:**
```python
elif condition_type == "regex":
    try:
        return bool(re.search(condition_value, input_str))
    except re.error as e:
        raise ValueError(f"ConditionalModule: invalid regex pattern '{condition_value}': {e}") from e
```

---

## ISSUE 17 — `transform.py`: `json_parse` transformation raises unhandled `json.JSONDecodeError`

**File:** `backend/app/engine/modules/transform.py`
**Lines:** 21–25

**Problem:**
```python
if transformation == "json_parse":
    if isinstance(input_value, str):
        output = json.loads(input_value)   # raises JSONDecodeError on bad input
    else:
        output = input_value
```
If `input_value` is an invalid JSON string, `json.loads` raises `json.JSONDecodeError`, which propagates and marks the workflow as failed with a confusing low-level error.

**Fix:** Catch and re-raise with context:

```python
if transformation == "json_parse":
    if isinstance(input_value, str):
        try:
            output = json.loads(input_value)
        except json.JSONDecodeError as e:
            raise ValueError(f"TransformModule: Failed to parse JSON input: {e}") from e
    else:
        output = input_value
```

---

## ISSUE 18 — `registry.py`: `InputModule` is defined inside `registry.py` — violates single-responsibility principle

**File:** `backend/app/engine/modules/registry.py`
**Lines:** 11–17

**Problem:**
`InputModule` is defined directly inside `registry.py` rather than in its own file (like all other modules). This is inconsistent and makes it harder to find, test, or extend `InputModule`. It also means `registry.py` mixes module *definition* with module *registration*.

**Fix:** Move `InputModule` to a new file `backend/app/engine/modules/input.py`:

```python
# input.py
from typing import Any
from app.engine.modules.base import BaseModule
from app.engine.context import ExecutionContext


class InputModule(BaseModule):
    """Input module - passes through the workflow's initial input."""

    module_type = "input"

    async def execute(
        self,
        config: dict[str, Any],
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        return {"output": inputs.get("input", context.input_data)}
```

Then in `registry.py`:
```python
from app.engine.modules.input import InputModule
```

---

## ISSUE 19 — `registry.py`: `get_module` instantiates a new object every call — stateless modules should be singletons

**File:** `backend/app/engine/modules/registry.py`
**Lines:** 33–38

**Problem:**
```python
@classmethod
def get_module(cls, node_type: str) -> BaseModule:
    module_class = cls._modules.get(node_type)
    if module_class is None:
        raise ValueError(f"Unknown module type: {node_type}")
    return module_class()   # New instance every call
```
All modules are effectively stateless (no `__init__` state), so creating a new instance on every `get_module()` call in the hot execution loop is wasteful.

**Fix:** Cache module instances in a `_instances` dict:

```python
_instances: dict[str, BaseModule] = {}

@classmethod
def get_module(cls, node_type: str) -> BaseModule:
    if node_type not in cls._instances:
        module_class = cls._modules.get(node_type)
        if module_class is None:
            raise ValueError(f"Unknown module type: {node_type}")
        cls._instances[node_type] = module_class()
    return cls._instances[node_type]
```

> **Note:** Only do this if modules have no per-execution mutable state (they don't currently, but verify before applying).

---

## ISSUE 20 — `executor.py`: `_skip_subtree` is recursive and can overflow stack on deep graphs

**File:** `backend/app/engine/executor.py`
**Lines:** 147–154

**Problem:**
```python
def _skip_subtree(self, dag, node_id, context):
    context.skip_node(node_id)
    for child_id in dag.get_children(node_id):
        parents = dag.get_parents(child_id)
        if all(context.is_skipped(p) for p in parents):
            self._skip_subtree(dag, child_id, context)   # recursive
```
Same Python stack overflow risk as Issue 8 for deep subtrees.

**Fix:** Rewrite iteratively using a stack:

```python
def _skip_subtree(self, dag: DAGBuilder, start_node_id: str, context: ExecutionContext):
    """Iteratively skip a node and all its descendants."""
    stack = [start_node_id]
    while stack:
        node_id = stack.pop()
        context.skip_node(node_id)
        for child_id in dag.get_children(node_id):
            parents = dag.get_parents(child_id)
            if all(context.is_skipped(p) for p in parents):
                stack.append(child_id)
```

---

## Summary Table

| # | File | Severity | Category | One-Line Description |
|---|------|----------|----------|----------------------|
| 1 | executor.py | Low | Style | Broken import grouping |
| 2 | executor.py | Medium | Bug | `start_time` assignment placement risk |
| 3 | executor.py | Medium | Bug | Wrong `node_type` in skipped trace entries |
| 4 | executor.py | High | Bug | Fragile `'context' in locals()` pattern |
| 5 | executor.py | Medium | Bug | `token_usage` not saved on failure path |
| 6 | http_request.py | High | Bug | HTTP errors silently succeed |
| 7 | http_request.py | Medium | Bug | Empty URL causes cryptic error |
| 8 | dag_builder.py | Medium | Performance/Bug | Recursive DFS cycle detection — stack overflow risk + double-detection |
| 9 | dag_builder.py | High | Bug | Duplicate edges corrupt in-degree and cause false cycle errors |
| 10 | context.py | Medium | Logic | `get_final_output` returns last-inserted not terminal-output node |
| 11 | context.py | High | Bug | Parent output silently dropped if no `output`/`response` key |
| 12 | agent.py | High | Bug | Outdated/incorrect model names (gpt-4.1-mini, claude-3-haiku) |
| 13 | agent.py | Medium | Performance | New HTTP client created per execution |
| 14 | agent.py | High | Bug | Gemini `usage_metadata` may be None → AttributeError |
| 15 | agent.py | High | Bug | `response.text` raises on blocked Gemini responses |
| 16 | conditional.py | Medium | Bug | Invalid regex causes unhandled exception |
| 17 | transform.py | Medium | Bug | `json_parse` JSONDecodeError propagates unhandled |
| 18 | registry.py | Low | Architecture | `InputModule` defined in wrong file |
| 19 | registry.py | Low | Performance | Module instantiated on every call — should be singleton |
| 20 | executor.py | Medium | Bug | `_skip_subtree` recursive — stack overflow risk on deep graphs |
