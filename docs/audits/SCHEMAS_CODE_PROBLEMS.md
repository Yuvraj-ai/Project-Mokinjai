# Backend Schemas Code Problems And Fix Plan

Scope reviewed: `backend/app/schemas`.

This file is written as an implementation handoff for a CLI coding agent. Fix the problems in priority order, keep changes scoped, and add tests that prove invalid API payloads are rejected before they reach routers/models.

## Current Files

- `backend/app/schemas/__init__.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/execution.py`
- `backend/app/schemas/knowledge.py`
- `backend/app/schemas/user.py`
- `backend/app/schemas/workflow.py`
- `backend/app/schemas/workspace.py`

## Problem 1: `execution.py` Does Not Compile

Evidence:

- `python -m py_compile backend/app/schemas/*.py` fails.
- `backend/app/schemas/execution.py` has stray corrupted lines:

  ```python
  nResponse]
      total: int
  ```

- `ExecutionResponse.cost_usd` uses `Decimal`, but `Decimal` is not imported. This is not caught by `py_compile`, but the module will fail when imported after the syntax error is removed.

Why this is a problem:

- Any route importing `ExecutionResponse` or `ExecutionListResponse` cannot import cleanly.
- `backend/app/routers/executions.py` depends on this schema module, so the API startup path is blocked.

Proper fix:

1. Remove the corrupted lines 47-48.
2. Add the missing import:

   ```python
   from decimal import Decimal
   ```

3. Re-run both compile and import checks.

Suggested verification:

```bash
python -m py_compile backend/app/schemas/execution.py
python -c "from app.schemas.execution import ExecutionResponse, ExecutionListResponse"
```

## Problem 2: Mutable Defaults Should Use `Field(default_factory=...)`

Evidence:

- `workflow.py` uses mutable/default object values:
  - `NodeSchema.data: dict[str, Any] = {}`
  - `FlowDefinition.nodes: list[NodeSchema] = []`
  - `FlowDefinition.edges: list[EdgeSchema] = []`
  - `WorkflowCreate.flow_definition: FlowDefinition = FlowDefinition()`
- `execution.py` uses `ExecuteRequest.input_data: dict[str, Any] = {}`.
- `knowledge.py` uses `KnowledgeBaseCreate.config: dict[str, Any] = {}`.

Why this is a problem:

- Pydantic v2 usually copies mutable defaults, but `default_factory` is still the clearer and safer contract.
- Static analysis tools and future maintainers will flag plain `{}` and `[]` defaults.
- `FlowDefinition()` as a default instance is especially easy to misunderstand.

Proper fix:

Use `Field(default_factory=...)`:

```python
from pydantic import BaseModel, Field

class NodeSchema(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)

class FlowDefinition(BaseModel):
    nodes: list[NodeSchema] = Field(default_factory=list)
    edges: list[EdgeSchema] = Field(default_factory=list)

class WorkflowCreate(BaseModel):
    flow_definition: FlowDefinition = Field(default_factory=FlowDefinition)

class ExecuteRequest(BaseModel):
    input_data: dict[str, Any] = Field(default_factory=dict)

class KnowledgeBaseCreate(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
```

Suggested tests:

- Create two schema instances and mutate one instance's dict/list; assert the other instance is unchanged.

## Problem 3: Request Schemas Accept Unknown Fields Silently

Evidence:

- All schemas inherit plain `BaseModel`.
- Pydantic's default behavior is to ignore extra fields.
- Create/update schemas currently allow clients to send misspelled or unsupported fields without a validation error.

Why this is a problem:

- Bad frontend payloads can look successful while fields are ignored.
- Typos like `flow_defintion`, `usr_id`, or `nam` are silently dropped.
- Security-sensitive request bodies should reject unexpected fields.

Proper fix:

Add strict request schema config:

```python
from pydantic import BaseModel, ConfigDict

class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

Then inherit request/input schemas from it:

- `RegisterRequest`
- `LoginRequest`
- `RefreshRequest`
- `WorkspaceCreate`
- `WorkspaceUpdate`
- `MemberAdd`
- `WorkflowCreate`
- `WorkflowUpdate`
- `ExecuteRequest`
- `KnowledgeBaseCreate`

Do not necessarily apply `extra="forbid"` to response schemas unless you want response construction to be strict too.

Suggested tests:

- Posting a request with an unknown field returns `422`.
- Existing valid requests still pass.

## Problem 4: Role, Status, Type, And Token Fields Are Plain Strings

Evidence:

- `MemberAdd.role` is `str`.
- `MemberResponse.role` is `str`.
- `WorkflowResponse.status` is `str`.
- `ExecutionResponse.status` and `ExecutionResponse.trigger_type` are `str`.
- `NodeExecutionLog.status` is `str`.
- `KnowledgeBaseCreate.type`, `KnowledgeBaseResponse.type`, and `DocumentResponse.status` are `str`.
- `TokenResponse.token_type` is `str`.

Why this is a problem:

- Invalid values can enter or leave the API contract.
- `MemberAdd.role` can accept `"owner"` or arbitrary strings, which contributes to privilege escalation in `workspaces.py`.
- Invalid filters and persisted statuses are harder to catch.

Proper fix:

Use shared `Literal` aliases or enums.

Example:

```python
from typing import Literal

WorkspaceRole = Literal["owner", "admin", "editor", "viewer"]
AssignableWorkspaceRole = Literal["admin", "editor", "viewer"]
WorkflowStatus = Literal["draft", "published", "archived"]
ExecutionStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
ExecutionTriggerType = Literal["manual", "api", "scheduled", "webhook"]
KnowledgeBaseType = Literal["document", "url", "api"]
DocumentStatus = Literal["processing", "indexed", "failed"]
TokenType = Literal["bearer"]

class MemberAdd(StrictRequestModel):
    role: AssignableWorkspaceRole = "viewer"

class MemberResponse(BaseModel):
    role: WorkspaceRole
```

Important:

- If owners must be assignable, do it through a dedicated owner-transfer schema/route rather than the generic `MemberAdd` schema.
- Keep these schema literals aligned with database check constraints and RBAC role hierarchy.

Suggested tests:

- Invalid role/type/status values return `422`.
- `MemberAdd(role="owner")` is rejected unless the app intentionally adds a dedicated owner-transfer flow.

## Problem 5: Text Fields Lack Length And Blank-String Validation

Evidence:

- `RegisterRequest.password` is plain `str`.
- `RegisterRequest.name`, `WorkspaceCreate.name`, `WorkflowCreate.name`, and `KnowledgeBaseCreate.name` are unconstrained strings.
- Update schemas allow blank names.
- `avatar_url`, `sourceHandle`, `targetHandle`, node IDs, edge IDs, and file names have no length constraints.

Why this is a problem:

- Empty or whitespace-only names can be stored.
- Passwords can be trivially short.
- Very large strings can be accepted into request bodies and persisted.

Proper fix:

Use `Field` constraints and validators where needed:

```python
from pydantic import Field, field_validator

class RegisterRequest(StrictRequestModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=255)

class WorkspaceCreate(StrictRequestModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value
```

Apply similar constraints:

- Workflow names: `1..255`
- Knowledge base names: `1..255`
- Descriptions: reasonable max length, or document that they are unbounded text
- User names: max `255`
- Avatar URL: use `HttpUrl` or constrained string
- Node/edge IDs: non-empty bounded strings

Suggested tests:

- Empty string and whitespace-only names return `422`.
- Short passwords return `422`.
- Overlong fields return `422`.

## Problem 6: `UserResponse.email` Is Typed As `str` While `EmailStr` Is Imported But Unused

Evidence:

- `backend/app/schemas/user.py` imports `EmailStr`.
- `UserResponse.email` is typed as `str`.

Why this is a problem:

- The import is stale or the response type is weaker than intended.
- API docs do not communicate that `email` is an email-shaped value.

Proper fix:

Use the imported type:

```python
class UserResponse(BaseModel):
    email: EmailStr
```

Also use `EmailStr` anywhere email is accepted or returned.

Suggested checks:

- Static unused-import check no longer flags `EmailStr`.
- OpenAPI schema shows email format.

## Problem 7: Update Schemas Cannot Enforce Empty-Payload Behavior Alone

Evidence:

- `WorkspaceUpdate.name` defaults to `None`.
- `WorkflowUpdate.name`, `description`, and `flow_definition` all default to `None`.
- Routers currently check `if request.name is not None`, so omitted fields and intentional `null` are treated the same.

Why this is a problem:

- Empty update payloads are accepted by schemas.
- Clients cannot intentionally clear nullable fields such as `description` if routers only check for `is not None`.

Proper fix:

Use schema plus router field tracking:

```python
if not request.model_fields_set:
    raise BadRequestException("No update fields provided")

if "description" in request.model_fields_set:
    workflow.description = request.description
```

Optional schema-level helper:

```python
from pydantic import model_validator

class NonEmptyUpdateModel(BaseModel):
    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self
```

Use this carefully: some Pydantic versions warn about accessing `model_fields_set` inside validators. Router-level validation is acceptable if covered by tests.

Suggested tests:

- `{}` update payload returns `400` or `422`, based on the chosen layer.
- `{"description": null}` clears workflow description.
- `{"name": ""}` is rejected.

## Problem 8: Flow Definition Schema Does Not Validate Graph Integrity

Evidence:

- `FlowDefinition` only contains `nodes` and `edges`.
- `NodeSchema.id` and `EdgeSchema.id` are plain strings.
- Duplicate node IDs are possible.
- `DAGBuilder` later converts nodes using `{n["id"]: n for n in nodes}`, so duplicate node IDs silently overwrite earlier nodes.
- Edge source/target references are only checked later by `DAGBuilder.validate()`.

Why this is a problem:

- Invalid workflows can be saved and only fail at execution time.
- Duplicate node IDs can corrupt workflow shape silently.
- API clients receive delayed errors instead of validation feedback.

Proper fix:

Add a `FlowDefinition` model validator:

```python
from pydantic import model_validator

class FlowDefinition(BaseModel):
    nodes: list[NodeSchema] = Field(default_factory=list)
    edges: list[EdgeSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self):
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Node IDs must be unique")

        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("Edge IDs must be unique")

        node_id_set = set(node_ids)
        for edge in self.edges:
            if edge.source not in node_id_set:
                raise ValueError(f"Edge {edge.id} references unknown source node")
            if edge.target not in node_id_set:
                raise ValueError(f"Edge {edge.id} references unknown target node")
        return self
```

Cycle validation can remain in `DAGBuilder`, or move to schema validation if workflows should be rejected on create/update rather than at execute/publish time.

Suggested tests:

- Duplicate node IDs return `422`.
- Duplicate edge IDs return `422`.
- Edge with missing source/target returns `422`.

## Problem 9: Node `type` And `data` Are Too Loosely Defined

Evidence:

- `NodeSchema.type` is a plain string.
- `NodeSchema.data` is `dict[str, Any]`.
- The engine registry supports known node types: `input`, `agent`, `prompt`, `output`, `conditional`, `transform`, and `http_request`.
- Backend modules expect specific config keys such as `provider`, `model`, `systemPrompt`, `conditionType`, `url`, `method`, `headers`, and `body`.

Why this is a problem:

- Unknown node types are accepted by schemas and fail later in the executor.
- Invalid node configs are accepted and may fail during execution.
- Frontend/backend naming can drift, for example `system_prompt` versus `systemPrompt`.

Proper fix:

Minimum:

```python
NodeType = Literal[
    "input",
    "agent",
    "prompt",
    "output",
    "conditional",
    "transform",
    "http_request",
]

class NodeSchema(BaseModel):
    type: NodeType
```

Better:

- Add typed config schemas per node type.
- Use a discriminated union based on `type`.
- Keep these schemas aligned with `ModuleRegistry`.

Example direction:

```python
class HttpRequestData(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    url: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
```

Suggested tests:

- Unknown node type returns `422`.
- Invalid HTTP method returns `422`.
- Agent provider outside supported providers returns `422`.

## Problem 10: Response Schemas Do Not Fully Match Router/Model Behavior

Evidence:

- `WorkflowResponse.flow_definition` is optional and defaults to `None`, but workflow detail routes try to hydrate it from MongoDB.
- Workflow list routes return `Workflow` ORM objects directly, so `flow_definition` will be `None` in list responses.
- `ExecutionResponse.execution_trace` is optional, but execution detail routes currently return the SQL model directly and do not hydrate the Mongo trace.
- `DocumentResponse` omits fields that may be useful or intentionally hidden, such as `metadata_`, `file_url`, `updated_at`, and `atlas_document_ids`.

Why this is a problem:

- API clients cannot tell whether `None` means "not loaded", "missing", or "empty".
- The same schema is used for list/detail responses even when detail responses are richer.
- Optional fields hide route implementation gaps.

Proper fix:

Use separate list/detail response schemas where payload shape differs:

```python
class WorkflowSummaryResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    status: WorkflowStatus
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

class WorkflowDetailResponse(WorkflowSummaryResponse):
    flow_definition: FlowDefinition | dict[str, Any]
```

And:

```python
class ExecutionSummaryResponse(BaseModel):
    ...

class ExecutionDetailResponse(ExecutionSummaryResponse):
    execution_trace: dict[str, Any] | None = None
```

Suggested tests:

- Workflow list response does not claim to include full flow data unless it actually does.
- Workflow detail response includes flow data after router hydration.
- Execution detail response includes trace data after router hydration.

## Problem 11: `Decimal` Serialization For `cost_usd` Needs An Explicit API Contract

Evidence:

- `ExecutionResponse.cost_usd` is typed as `Decimal | None`.
- Frontend/API clients may expect either a JSON string or number.
- Pydantic/FastAPI can serialize `Decimal`, but the exact JSON representation should be intentional for money-like values.

Why this is a problem:

- Clients can break if `cost_usd` changes between string and number representations.
- Money values should avoid accidental precision loss.

Proper fix:

Choose one:

Option A, precision-preserving:

```python
from decimal import Decimal
from pydantic import field_serializer

class ExecutionResponse(BaseModel):
    cost_usd: Decimal | None = None

    @field_serializer("cost_usd")
    def serialize_cost(self, value: Decimal | None):
        return str(value) if value is not None else None
```

Option B, frontend-friendly number:

```python
cost_usd: float | None = None
```

Recommended:

- Use string serialization for money/usage cost precision unless the frontend already expects a number.

Suggested tests:

- API JSON for `cost_usd=Decimal("0.000123")` matches the chosen representation.

## Problem 12: `__init__.py` Does Not Provide A Stable Schema Export Surface

Evidence:

- `backend/app/schemas/__init__.py` is empty.
- Routers import directly from individual schema files.

Why this is a problem:

- This is not a runtime bug, but it makes schema discovery harder.
- Future agents may be unsure which schemas are public API contracts.

Proper fix:

Optional, if the project wants package-level exports:

```python
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.execution import ExecuteRequest, ExecutionListResponse, ExecutionResponse
from app.schemas.knowledge import DocumentResponse, KnowledgeBaseCreate, KnowledgeBaseResponse
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.workflow import FlowDefinition, WorkflowCreate, WorkflowListResponse, WorkflowResponse, WorkflowUpdate
from app.schemas.workspace import MemberAdd, MemberResponse, WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate

__all__ = [...]
```

If direct module imports are preferred, leave it empty and document that convention.

Suggested checks:

- Importing `app.schemas` should not introduce circular imports.

## Recommended Implementation Order

1. Fix `execution.py` syntax corruption and import `Decimal`.
2. Replace mutable defaults with `Field(default_factory=...)`.
3. Add strict request base model with `extra="forbid"`.
4. Add `Literal` or enum types for roles, statuses, trigger types, token type, knowledge type, document status, and node type.
5. Add string length and blank-string validation for user-facing names/passwords/IDs.
6. Add graph validation to `FlowDefinition`.
7. Decide whether to split list/detail response schemas.
8. Define `cost_usd` serialization.
9. Optionally add package-level schema exports.
10. Add focused schema and route validation tests.

## Verification Commands

Run these after implementing fixes:

```bash
python -m py_compile backend/app/schemas/*.py
python - <<'PY'
from app.schemas.auth import RegisterRequest
from app.schemas.execution import ExecutionResponse, ExecutionListResponse
from app.schemas.workflow import FlowDefinition, WorkflowCreate
from app.schemas.workspace import MemberAdd
from app.schemas.knowledge import KnowledgeBaseCreate
print("schema imports ok")
PY
pytest backend/tests -q
```

If running from inside `backend`, use:

```bash
cd backend
python - <<'PY'
from app.schemas.auth import RegisterRequest
from app.schemas.execution import ExecutionResponse, ExecutionListResponse
from app.schemas.workflow import FlowDefinition, WorkflowCreate
from app.schemas.workspace import MemberAdd
from app.schemas.knowledge import KnowledgeBaseCreate
print("schema imports ok")
PY
pytest tests -q
```

## Notes For The CLI Agent

- Do not edit unrelated frontend files.
- Preserve existing user-owned uncommitted changes unless a schema fix must build on them.
- Keep schemas aligned with routers, models, `ModuleRegistry`, and database constraints.
- Prefer schema tests for pure validation behavior and route tests for HTTP `422` behavior.
- Mock external services in route tests; schema tests should not need database, Redis, or MongoDB.
