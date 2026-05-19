# Mokinjay Backend - Comprehensive Codebase Walkthrough

## Table of Contents
1. [Overall Architecture](#overall-architecture)
2. [Configuration](#configuration)
3. [Database Setup](#database-setup)
4. [Data Models (Database Schema)](#data-models--database-schema)
5. [API Schemas (Pydantic)](#api-schemas-pydantic)
6. [API Routes (Routers)](#api-routes-routers)
7. [Workflow Execution Engine](#workflow-execution-engine)
8. [Module System (Node Types)](#module-system-node-types)
9. [Middleware & Security](#middleware--security)
10. [Other Components](#other-components)
11. [Request Flow Example](#request-flow-example)

---

## Overall Architecture

Mokinjay backend is a **FastAPI-based workflow engine** that allows users to visually design and execute AI-powered workflows. The architecture follows a **layered design**:

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (React + React Flow) - http://localhost:5173           │
└────────────────┬────────────────────────────────────────────────┘
                 │ REST API + WebSocket
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│ Backend (FastAPI) - http://localhost:8000                       │
│  ├─ main.py (App entry point)                                   │
│  ├─ routers/ (API endpoints)                                    │
│  ├─ middleware/ (Auth, RBAC)                                    │
│  ├─ engine/ (Workflow execution)                                │
│  ├─ services/ (Business logic)                                  │
│  └─ utils/ (Helpers, security)                                  │
└────┬───────────────────┬─────────────────────────┬──────────────┘
     │                   │                         │
     ↓                   ↓                         ↓
┌──────────────────┐ ┌──────────────────┐ ┌─────────────────┐
│ PostgreSQL/      │ │ MongoDB Atlas    │ │ Redis           │
│ SQLite           │ │ (Flow defs,      │ │ (Celery queue,  │
│ (Metadata)       │ │  traces, vectors)│ │  WebSocket pub) │
└──────────────────┘ └──────────────────┘ └─────────────────┘
     │
     └─ Relational data: Users, Workspaces, Workflows, Executions
     
┌─────────────────────────────────────────────────────────────────┐
│ Celery Worker - background async tasks                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration

**File**: `app/config.py`

The `Settings` class loads environment variables and defines all app config:

```python
class Settings(BaseSettings):
    ENVIRONMENT: Literal["local", "test", "production"] = "local"
    
    # Database - SQLite in dev, PostgreSQL in prod
    DATABASE_URL: str = "sqlite+aiosqlite:///./agentbuilder.db"
    
    # MongoDB - stores workflow definitions (nodes/edges) and execution traces
    MONGO_URL: str = ""
    MONGO_DB_NAME: str = "lane1"
    
    # Redis - Celery queue + WebSocket pub/sub
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT tokens for authentication
    JWT_SECRET_KEY: SecretStr = "dev-only-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # LLM API keys for agent nodes
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    
    # CORS for frontend
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
```

**Key Functions**:
- `get_settings()` - Cached singleton that returns the Settings instance

**Key Points**:
- Uses Pydantic v2 `BaseSettings` to load from `.env` file
- Production mode validates JWT secret is changed and MongoDB is configured
- Supports SQLite for dev, PostgreSQL for production

---

## Database Setup

**File**: `app/database.py`

Configures SQLAlchemy async ORM:

```python
# Base declarative class for all models
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)

# Global async engine and session factory
engine = None
async_session = None

def init_db(settings: Settings):
    global engine, async_session
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    
    # SQLite-specific: enable foreign key constraints
    if settings.DATABASE_URL.startswith("sqlite"):
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    
    # Create async session factory
    async_session = async_sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )

# Dependency injection for routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Key Concepts**:
- **Async SQLAlchemy**: All DB operations are non-blocking
- **get_db()**: FastAPI dependency that provides a session to routes
- **Foreign Keys**: Enforced in SQLite and PostgreSQL
- **Naming Convention**: Automatic constraint naming (ix_, uq_, fk_, etc.)

---

## Data Models (Database Schema)

**Directory**: `app/models/`

All models inherit from `Base` and map to database tables:

### 1. **User Model** (`user.py`)

```python
class User(Base):
    __tablename__ = "users"
    
    id: str = PrimaryKey (UUID)
    email: str = Unique, indexed
    hashed_password: str
    name: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime
    
    # Relationships
    owned_workspaces = relationship("Workspace")  # One user owns many workspaces
    workspace_memberships = relationship("WorkspaceMember")  # User can be member of many workspaces
```

**Purpose**: Stores user accounts, authentication credentials.

---

### 2. **Workspace Models** (`workspace.py`)

```python
class Workspace(Base):
    __tablename__ = "workspaces"
    
    id: str = UUID
    name: str
    owner_id: str = ForeignKey("users.id")
    created_at: datetime
    updated_at: datetime
    
    # Relationships
    owner = relationship("User")  # Who owns this workspace
    members = relationship("WorkspaceMember")  # All members (owner + collaborators)
    workflows = relationship("Workflow")  # All workflows in this workspace
    knowledge_bases = relationship("KnowledgeBase")  # RAG knowledge bases
    api_keys = relationship("ApiKey")  # API keys for this workspace

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"  # Join table
    
    workspace_id: str = ForeignKey("workspaces.id")
    user_id: str = ForeignKey("users.id")
    role: str  # "owner", "admin", "editor", "viewer"
```

**Purpose**: Multi-user workspaces with role-based access control.
**Roles**:
- `owner` - Can delete workspace, manage members
- `admin` - Can edit workflows, manage collaborators
- `editor` - Can create/edit workflows
- `viewer` - Can only view/run workflows

---

### 3. **Workflow Models** (`workflow.py`)

```python
class Workflow(Base):
    __tablename__ = "workflows"
    
    id: str = UUID
    workspace_id: str = ForeignKey
    name: str
    description: str | None
    mongo_flow_id: str | None  # Reference to MongoDB document (nodes/edges)
    status: str  # "draft", "published", "archived"
    version: int  # Current version number
    created_by: str = ForeignKey("users.id")
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    
    # Relationships
    workspace = relationship("Workspace")
    versions = relationship("WorkflowVersion")  # Version history
    executions = relationship("Execution")  # All runs of this workflow

class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"  # Version history
    
    id: str = UUID
    workflow_id: str = ForeignKey
    version: int
    mongo_flow_id: str  # Reference to MongoDB (different flow definition for each version)
    changelog: str | None
    created_by: str
    created_at: datetime
```

**Purpose**: Stores workflow metadata. Actual workflow definition (nodes/edges) is stored in MongoDB.
**Why Two Databases?**
- **PostgreSQL**: Structured metadata (names, versions, user ownership, execution logs)
- **MongoDB**: Flexible JSON storage for flow definitions (nodes have different configs)

---

### 4. **Execution Model** (`execution.py`)

```python
class Execution(Base):
    __tablename__ = "executions"
    
    id: str = UUID
    workflow_id: str | None = ForeignKey  # Which workflow was run
    workspace_id: str = ForeignKey
    workflow_version: int | None  # Which version was executed
    status: str  # "pending", "running", "completed", "failed", "cancelled"
    trigger_type: str | None  # "manual", "api", "scheduled", "webhook"
    input_data: dict | None  # User input to the workflow (JSON)
    output_data: dict | None  # Final result (JSON)
    error_message: str | None  # Error if failed
    mongo_trace_id: str | None  # Reference to MongoDB (detailed execution trace)
    execution_time_ms: int | None
    token_usage: dict | None  # LLM token counts
    cost_usd: Decimal | None  # Estimated cost
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    
    # Relationships
    workflow = relationship("Workflow")
```

**Purpose**: Logs every workflow execution. Stores metadata + references to detailed traces in MongoDB.

---

### 5. **Knowledge Base Models** (`knowledge.py`)

```python
class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    
    id: str = UUID
    workspace_id: str = ForeignKey
    name: str
    description: str | None
    type: str  # "document", "url", "api"
    config: dict  # Type-specific configuration (stored as JSON)
    created_at: datetime
    updated_at: datetime
    
    # Relationships
    documents = relationship("Document")

class Document(Base):
    __tablename__ = "documents"
    
    id: str = UUID
    knowledge_base_id: str = ForeignKey
    filename: str | None
    file_url: str | None
    file_size: int | None
    mime_type: str
    content: str | None
    metadata_: dict | None  # Custom metadata
    atlas_document_ids: list | None  # Vector store references (MongoDB Atlas)
    status: str  # "processing", "indexed", "failed"
    created_at: datetime
    updated_at: datetime
```

**Purpose**: Stores documents for RAG (Retrieval Augmented Generation) knowledge bases.
**Flow**:
1. User uploads document
2. Document is indexed in MongoDB Atlas (with vector embeddings)
3. At runtime, Knowledge node retrieves relevant documents via vector search

---

## API Schemas (Pydantic)

**Directory**: `app/schemas/`

Pydantic models for request/response validation:

### Workflow Schemas (`workflow.py`)

```python
# Node definition (part of workflow)
class NodeSchema(BaseModel):
    id: str  # Unique node ID
    type: NodeType  # "input", "agent", "prompt", "output", "conditional", "transform", "http_request", "knowledge"
    data: dict[str, Any]  # Node-specific configuration
    position: PositionSchema  # {x, y} for canvas rendering

# Edge definition (connection between nodes)
class EdgeSchema(BaseModel):
    id: str
    source: str  # Source node ID
    target: str  # Target node ID
    sourceHandle: str | None
    targetHandle: str | None

# Complete flow definition
class FlowDefinition(BaseModel):
    nodes: list[NodeSchema]
    edges: list[EdgeSchema]

# Request to create workflow
class WorkflowCreate(BaseModel):
    name: str  # 1-255 chars
    description: str | None
    flow_definition: FlowDefinition

# Request to update workflow
class WorkflowUpdate(BaseModel):
    name: str | None
    description: str | None
    flow_definition: FlowDefinition | None

# Response from API
class WorkflowResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    flow_definition: dict | None
    status: WorkflowStatus  # "draft", "published", "archived"
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
```

---

## API Routes (Routers)

**Directory**: `app/routers/`

Each router defines API endpoints for a resource:

### Main Entry Point (`main.py`)

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Mokinjai API", version="0.1.0", lifespan=lifespan)
    
    # Add CORS middleware
    app.add_middleware(CORSMiddleware, ...)
    
    # Include all routers
    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(users.router, prefix="/api/users")
    app.include_router(workspaces.router, prefix="/api/workspaces")
    app.include_router(workflows.router, prefix="/api/workspaces/{workspace_id}/workflows")
    app.include_router(executions.router, prefix="/api/workspaces/{workspace_id}")
    app.include_router(knowledge.router, prefix="/api/workspaces/{workspace_id}/knowledge-bases")
    
    # Health checks
    @app.get("/health")
    async def health_check(): return {"status": "ok"}
    
    @app.get("/ready")
    async def readiness_check(): # Check DB + Redis connectivity
    
    # WebSocket for real-time execution updates
    @app.websocket("/ws/executions/{execution_id}")
    async def ws_execution(websocket: WebSocket, execution_id: str): ...
    
    return app
```

### Auth Router (`routers/auth.py`)

**Endpoints**:

```python
POST /api/auth/register
{
    "email": "user@example.com",
    "password": "secret",
    "name": "John Doe"
}
→ TokenResponse {
    "access_token": "jwt-token...",
    "refresh_token": "jwt-token..."
}

POST /api/auth/login
{
    "email": "user@example.com",
    "password": "secret"
}
→ TokenResponse

POST /api/auth/refresh
{
    "refresh_token": "jwt-token..."
}
→ TokenResponse  # New access token

GET /api/auth/me  (requires Bearer token)
→ UserResponse { id, email, name, ... }
```

**Functions**:

```python
async def register(request: RegisterRequest, db: AsyncSession):
    # Check if email already exists
    # Hash password using bcrypt
    # Create User record
    # Generate JWT tokens
    # Return tokens

async def login(request: LoginRequest, db: AsyncSession):
    # Find user by email
    # Verify password hash
    # Generate JWT tokens
    # Return tokens

async def refresh_token(request: RefreshRequest, db: AsyncSession):
    # Decode refresh token
    # Verify it's a refresh token (not access token)
    # Generate new access token
    # Return new token
```

---

### Workflows Router (`routers/workflows.py`)

**Endpoints**:

```python
POST /api/workspaces/{workspace_id}/workflows
{
    "name": "My AI Workflow",
    "description": "...",
    "flow_definition": {
        "nodes": [...],
        "edges": [...]
    }
}
→ WorkflowResponse

GET /api/workspaces/{workspace_id}/workflows
→ WorkflowListResponse { workflows: [...], total: 50 }

GET /api/workspaces/{workspace_id}/workflows/{workflow_id}
→ WorkflowResponse

PUT /api/workspaces/{workspace_id}/workflows/{workflow_id}
{
    "name": "Updated name",
    "flow_definition": {...}
}
→ WorkflowResponse

DELETE /api/workspaces/{workspace_id}/workflows/{workflow_id}
→ 204 No Content

POST /api/workspaces/{workspace_id}/workflows/{workflow_id}/execute
{
    "input_data": {"user_query": "Hello"}
}
→ ExecutionResponse { id: "exec-123", status: "pending", ... }
```

**Key Functions**:

```python
async def create_workflow(workspace_id: str, request: WorkflowCreate, db: AsyncSession, current_user: User):
    # Verify user is member of workspace
    # Create Workflow record
    # Save flow_definition to MongoDB
    # Set mongo_flow_id reference
    # Return WorkflowResponse

async def execute_workflow(workspace_id: str, workflow_id: str, request: ExecutionRequest, db: AsyncSession, current_user: User):
    # Create Execution record with status="pending"
    # Dispatch to Celery worker via Redis queue
    # Return ExecutionResponse with execution_id
```

---

### Executions Router (`routers/executions.py`)

**Endpoints**:

```python
GET /api/workspaces/{workspace_id}/executions
→ List all executions with pagination

GET /api/workspaces/{workspace_id}/executions/{execution_id}
→ ExecutionResponse (includes output_data and trace references)

GET /api/workspaces/{workspace_id}/executions/{execution_id}/trace
→ Detailed execution trace from MongoDB
```

---

## Workflow Execution Engine

**Directory**: `app/engine/`

The core execution logic that runs workflows:

### 1. **DAG Builder** (`dag_builder.py`)

Converts flow definition (nodes + edges) into a Directed Acyclic Graph and performs topological sort:

```python
class DAGBuilder:
    def __init__(self, flow_definition: dict):
        self.nodes = {n["id"]: n for n in flow_definition.get("nodes", [])}
        self.edges = flow_definition.get("edges", [])
        self.adjacency = defaultdict(list)  # node_id -> [child_ids]
        self.reverse_adjacency = defaultdict(list)  # node_id -> [parent_ids]
        self.in_degree = {nid: 0 for nid in self.nodes}  # Count of parents
    
    def detect_cycles(self) -> bool:
        """DFS to detect cycles - returns True if cycle found"""
        # Using DFS with recursion stack
    
    def topological_sort(self) -> list[str]:
        """Kahn's algorithm for topological sort
        Returns nodes in execution order (parents before children)
        Raises BadRequestException if cycle detected"""
    
    def validate(self):
        """Check for empty workflows, missing node references, etc."""
    
    def get_parents(self, node_id: str) -> list[str]:
        """Get all immediate parent nodes"""
    
    def get_children(self, node_id: str) -> list[str]:
        """Get all immediate child nodes"""
```

**Why?** Ensures nodes execute in correct order respecting dependencies.

---

### 2. **Execution Context** (`context.py`)

Manages state during workflow execution:

```python
class ExecutionContext:
    def __init__(self, input_data: dict[str, Any] | None = None):
        self.input_data = input_data  # Initial workflow input
        self.node_outputs = {}  # {node_id: {output_data}}
        self.trace = []  # Detailed log of each step
        self.total_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.skipped_nodes = set()  # For conditional branching
    
    def set_output(self, node_id: str, data: dict):
        """Store node output"""
        self.node_outputs[node_id] = data
    
    def get_inputs_for(self, node_id: str, parent_ids: list[str]) -> dict:
        """Collect outputs from parent nodes as input for this node"""
        # Nodes get their input from upstream nodes
    
    def add_trace_entry(self, node_id: str, node_type: str, status: str, inputs=None, outputs=None, error=None, duration_ms=None):
        """Log each step with timing, inputs, outputs, errors"""
        self.trace.append({
            "node_id": node_id,
            "node_type": node_type,
            "status": "completed" | "failed" | "skipped",
            "inputs": inputs,
            "outputs": outputs,
            "error": error,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def add_token_usage(self, usage: dict):
        """Accumulate LLM token usage"""
    
    def skip_node(self, node_id: str):
        """Mark node as skipped (for conditional branches)"""
    
    def get_final_output(self) -> dict:
        """Return the output node's data"""
```

---

### 3. **Workflow Executor** (`executor.py`)

Main execution engine:

```python
class WorkflowExecutor:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def execute(self, execution_id: str) -> Execution:
        # 1. Load execution record from DB
        # 2. Load workflow from DB
        # 3. Load flow definition from MongoDB
        # 4. Build DAG and validate
        # 5. Topologically sort nodes
        # 6. For each node in order:
        #    - Get module for node type
        #    - Collect inputs from parent nodes
        #    - Execute module async
        #    - Store output
        #    - Log trace entry
        #    - Handle conditional branching if needed
        # 7. On success:
        #    - Store output_data
        #    - Save trace to MongoDB
        #    - Set status = "completed"
        # 8. On error:
        #    - Set status = "failed"
        #    - Store error_message
        #    - Save partial trace
        # 9. Update execution record in DB
        # 10. Send completion event via WebSocket
        
        start_time = time.time()
        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        try:
            flow_def = await BlobService.get_blob(workflow.mongo_flow_id)
            dag = DAGBuilder(flow_def)
            dag.validate()
            sorted_nodes = dag.topological_sort()
            
            context = ExecutionContext(execution.input_data)
            
            for node_id in sorted_nodes:
                if context.is_skipped(node_id):
                    # Skip this node (from conditional)
                    context.add_trace_entry(node_id, node_type, "skipped")
                    continue
                
                node = dag.nodes[node_id]
                node_type = node["type"]
                node_config = node.get("data", {})
                
                # Get the module for this node type
                module = ModuleRegistry.get_module(node_type)
                
                # Collect inputs from parents
                parent_ids = dag.get_parents(node_id)
                inputs = context.get_inputs_for(node_id, parent_ids)
                
                # Execute node
                node_start = time.time()
                try:
                    output = await module.execute(node_config, inputs, context)
                    duration = int((time.time() - node_start) * 1000)
                    
                    context.set_output(node_id, output)
                    if node_type == "output":
                        context.mark_as_final_output(node_id)
                    
                    context.add_trace_entry(
                        node_id, node_type, "completed",
                        inputs=inputs, outputs=output, duration_ms=duration
                    )
                    
                    # Handle conditional branching
                    if node_type == "conditional" and "branch" in output:
                        self._handle_branching(dag, node_id, output["branch"], context)
                
                except Exception as e:
                    # Log failure and send WebSocket event
                    context.add_trace_entry(node_id, node_type, "failed", inputs=inputs, error=str(e))
                    raise
            
            # Success
            execution.status = "completed"
            execution.output_data = context.get_final_output()
            trace_data = {"nodes": context.trace}
            execution.mongo_trace_id = await BlobService.save_blob(trace_data)
            execution.execution_time_ms = int((time.time() - start_time) * 1000)
            execution.token_usage = context.total_token_usage
            execution.completed_at = datetime.now(timezone.utc)
        
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            # ... save partial trace
        
        await self.db.commit()
        return execution
    
    def _handle_branching(self, dag, node_id: str, branch: str, context: ExecutionContext):
        """Mark child nodes to skip based on conditional branch"""
        # If conditional says "skip branch B", mark those nodes as skipped
```

---

## Module System (Node Types)

**Directory**: `app/engine/modules/`

Each node type is a module that can be executed:

### Base Module (`base.py`)

```python
class BaseModule(ABC):
    """Base class for all node types"""
    
    module_type: str  # "agent", "prompt", "transform", etc.
    
    async def execute(
        self,
        config: dict[str, Any],  # Node configuration from user
        inputs: dict[str, Any],  # Data from parent nodes
        context: ExecutionContext,  # Execution state
    ) -> dict[str, Any]:
        """Execute the module and return output"""
        pass
```

### Agent Module (`agent.py`)

LLM integration - makes calls to OpenAI, Anthropic, or Gemini:

```python
class AgentModule(BaseModule):
    module_type = "agent"
    
    async def execute(self, config: dict, inputs: dict, context: ExecutionContext) -> dict:
        provider = config.get("provider")  # "openai", "anthropic", "gemini"
        model = config.get("model")  # "gpt-4o-mini", "claude-3-5-haiku", etc.
        system_prompt = config.get("systemPrompt")
        temperature = config.get("temperature", 0.1)
        max_tokens = config.get("maxTokens", 1000)
        
        input_text = inputs.get("input", "")  # Text from parent node
        
        if provider == "openai":
            # Call OpenAI API
            response = await openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": input_text}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract response
            output = response.choices[0].message.content
            usage = response.usage
            
            # Track token usage
            context.add_token_usage({
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            })
            
            return {
                "response": output,
                "output": output,  # For chaining to next nodes
                "token_usage": {...}
            }
```

### Prompt Module (`prompt.py`)

Template substitution with variable interpolation:

```python
class PromptModule(BaseModule):
    module_type = "prompt"
    
    async def execute(self, config: dict, inputs: dict, context: ExecutionContext) -> dict:
        template = config.get("template")  # "Hello {{name}}, how are {{status}}?"
        
        # Replace {{variable}} with values from inputs
        output = template
        for key, value in inputs.items():
            output = output.replace(f"{{{{{key}}}}}", str(value))
        
        return {
            "output": output,
            "template": template,
            "variables_used": list(inputs.keys())
        }
```

### Transform Module (`transform.py`)

Data transformation (parse JSON, extract fields, uppercase, split, etc.):

```python
class TransformModule(BaseModule):
    module_type = "transform"
    
    async def execute(self, config: dict, inputs: dict, context: ExecutionContext) -> dict:
        operation = config.get("operation")  # "json_parse", "extract_field", "uppercase", etc.
        data = inputs.get("input")
        
        if operation == "json_parse":
            result = json.loads(data)
        elif operation == "extract_field":
            field_name = config.get("field_name")
            result = data.get(field_name) if isinstance(data, dict) else None
        elif operation == "uppercase":
            result = str(data).upper()
        elif operation == "split":
            delimiter = config.get("delimiter", ",")
            result = str(data).split(delimiter)
        
        return {"output": result}
```

### Conditional Module (`conditional.py`)

Branching logic:

```python
class ConditionalModule(BaseModule):
    module_type = "conditional"
    
    async def execute(self, config: dict, inputs: dict, context: ExecutionContext) -> dict:
        condition_type = config.get("type")  # "contains", "equals", "regex", "greater_than", etc.
        condition_value = config.get("value")
        input_data = inputs.get("input")
        
        if condition_type == "equals":
            branch = "true" if str(input_data) == condition_value else "false"
        elif condition_type == "contains":
            branch = "true" if condition_value in str(input_data) else "false"
        elif condition_type == "regex":
            import re
            branch = "true" if re.search(condition_value, str(input_data)) else "false"
        elif condition_type == "greater_than":
            branch = "true" if float(input_data) > float(condition_value) else "false"
        
        return {"branch": branch}
        # This tells executor which child nodes to skip/execute
```

### HTTP Request Module (`http_request.py`)

Make external API calls:

```python
class HttpRequestModule(BaseModule):
    module_type = "http_request"
    
    async def execute(self, config: dict, inputs: dict, context: ExecutionContext) -> dict:
        method = config.get("method", "GET")
        url = config.get("url")
        headers = config.get("headers", {})
        body = config.get("body")
        
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=body)
            
            return {
                "status_code": response.status_code,
                "response": response.json(),
                "output": response.json()
            }
```

### Input Module (`input.py`)

Entry point - passes through workflow input:

```python
class InputModule(BaseModule):
    module_type = "input"
    
    async def execute(self, config: dict, inputs: dict, context: ExecutionContext) -> dict:
        # Just pass through the input
        return {"output": inputs.get("input", {})}
```

### Output Module (`output.py`)

Exit point - collects final result:

```python
class OutputModule(BaseModule):
    module_type = "output"
    
    async def execute(self, config: dict, inputs: dict, context: ExecutionContext) -> dict:
        # Capture final output
        return {"output": inputs.get("input")}
```

### Knowledge Module (`knowledge.py`)

RAG - retrieves relevant documents:

```python
class KnowledgeModule(BaseModule):
    module_type = "knowledge"
    
    async def execute(self, config: dict, inputs: dict, context: ExecutionContext) -> dict:
        knowledge_base_id = config.get("knowledge_base_id")
        query = inputs.get("input")
        top_k = config.get("top_k", 3)
        
        # Vector search in MongoDB Atlas
        results = await vector_search(knowledge_base_id, query, top_k)
        
        return {
            "output": results,
            "documents": [doc["content"] for doc in results],
            "sources": [doc["source"] for doc in results]
        }
```

### Module Registry (`registry.py`)

```python
class ModuleRegistry:
    _modules = {
        "input": InputModule(),
        "agent": AgentModule(),
        "prompt": PromptModule(),
        "output": OutputModule(),
        "conditional": ConditionalModule(),
        "transform": TransformModule(),
        "http_request": HttpRequestModule(),
        "knowledge": KnowledgeModule(),
    }
    
    @staticmethod
    def get_module(node_type: str) -> BaseModule:
        module = ModuleRegistry._modules.get(node_type)
        if not module:
            raise ValueError(f"Unknown node type: {node_type}")
        return module
```

---

## Middleware & Security

**Directory**: `app/middleware/`

### Auth Middleware (`auth.py`)

JWT token validation and current user extraction:

```python
def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """Dependency that validates JWT token and returns current user"""
    
    # Decode JWT token
    payload = decode_token(token)
    if payload is None:
        raise UnauthorizedException("Invalid token")
    
    user_id = payload.get("sub")
    # Fetch user from DB
    user = get_user_by_id(db, user_id)
    if not user:
        raise UnauthorizedException("User not found")
    
    return user

def require_workspace_access(workspace_id: str, role: str | None = None):
    """Verify user has access to workspace with optional role check"""
    async def dependency(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        member = await get_workspace_member(db, workspace_id, current_user.id)
        if not member:
            raise ForbiddenException("No access to this workspace")
        
        if role and member.role not in get_roles_with_permission(role):
            raise ForbiddenException(f"Requires {role} role")
        
        return current_user
    
    return dependency
```

### Security Utils (`utils/security.py`)

```python
def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash"""
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=30))
    to_encode.update({"exp": expire, "type": "access"})
    
    encoded = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded

def decode_token(token: str) -> dict | None:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

---

## Other Components

### WebSocket Handling (`websocket/execution_ws.py`)

Real-time updates during execution:

```python
async def execution_websocket(websocket: WebSocket, execution_id: str):
    await websocket.accept()
    
    # Subscribe to execution events via Redis pub/sub
    async with aioredis.from_url(settings.REDIS_URL) as redis:
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"execution:{execution_id}")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    event = json.loads(message["data"])
                    await websocket.send_json(event)  # Send to frontend
        finally:
            await pubsub.unsubscribe(f"execution:{execution_id}")
```

**Events sent**:
- `node_started`: Node started execution
- `node_completed`: Node finished with output
- `node_failed`: Node failed with error
- `execution_completed`: Workflow finished
- `execution_failed`: Workflow failed

---

### Background Workers (`workers/celery.py`)

Async task processing:

```python
@celery_app.task(bind=True)
def execute_workflow_task(self, execution_id: str):
    """Background task to execute workflow"""
    
    # Get async session
    # Create WorkflowExecutor
    # Run executor.execute(execution_id)
    # Send WebSocket events during execution
    
    # Celery retries on failure
    pass

@celery_app.task
def cleanup_old_executions():
    """Scheduled task to clean up old execution records"""
    pass
```

---

### Blob Service (`services/blob_service.py`)

Handles MongoDB storage:

```python
class BlobService:
    @staticmethod
    async def save_blob(data: dict) -> str:
        """Save data to MongoDB, return ObjectId"""
        collection = MongoManager.get_collection("flows")
        result = await collection.insert_one(data)
        return str(result.inserted_id)
    
    @staticmethod
    async def get_blob(blob_id: str) -> dict | None:
        """Retrieve data from MongoDB by ObjectId"""
        collection = MongoManager.get_collection("flows")
        doc = await collection.find_one({"_id": ObjectId(blob_id)})
        return doc
```

---

### Error Handling (`utils/errors.py`)

```python
class BadRequestException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class UnauthorizedException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=401, detail=detail)

class ForbiddenException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=403, detail=detail)

class NotFoundException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=404, detail=detail)
```

---

## Request Flow Example

### User Creates and Executes a Workflow

```
1. Frontend: User drops nodes and connects them on React Flow canvas
   └─ Sends POST /api/workspaces/{ws_id}/workflows
      {
          "name": "Extract and Summarize",
          "flow_definition": {
              "nodes": [
                  {"id": "1", "type": "input", "data": {}},
                  {"id": "2", "type": "prompt", "data": {"template": "Summarize: {{text}}"}},
                  {"id": "3", "type": "agent", "data": {"provider": "openai", "model": "gpt-4o-mini"}},
                  {"id": "4", "type": "output", "data": {}}
              ],
              "edges": [
                  {"source": "1", "target": "2"},
                  {"source": "2", "target": "3"},
                  {"source": "3", "target": "4"}
              ]
          }
      }

2. Backend (workflows.py):
   └─ Validate workflow
   └─ Save to DB (metadata: name, version, status)
   └─ Save flow_definition to MongoDB → get mongo_flow_id
   └─ Return WorkflowResponse with id and mongo_flow_id

3. Frontend: User clicks "Run" button
   └─ Sends POST /api/workspaces/{ws_id}/workflows/{wf_id}/execute
      {
          "input_data": {"text": "Long text to summarize..."}
      }

4. Backend (workflows.py execute_workflow):
   └─ Create Execution record in DB (status="pending")
   └─ Dispatch Celery task: execute_workflow_task(execution_id)
   └─ Return ExecutionResponse { id: "exec-123", status: "pending" }

5. Frontend: Connects WebSocket
   └─ ws.connect("ws://localhost:8000/ws/executions/exec-123")

6. Backend (Celery worker):
   └─ Call WorkflowExecutor.execute(execution_id)
   
   6a. Load execution, workflow from DB
   6b. Load flow_definition from MongoDB
   6c. DAGBuilder: Convert to graph, topological sort
       [1 (input)] → [2 (prompt)] → [3 (agent)] → [4 (output)]
   
   6d. ExecutionContext: Create with input_data
   
   6e. Execute node 1 (input):
       └─ InputModule.execute({}, {}, context)
       └─ Returns: {"output": input_data}
       └─ context.set_output("1", {...})
       └─ Send WebSocket: {"type": "node_completed", "node_id": "1"}
   
   6f. Execute node 2 (prompt):
       └─ Get inputs from parent: {"input": input_data}
       └─ PromptModule.execute(config, inputs, context)
       └─ Returns: {"output": "Summarize: Long text..."}
       └─ context.set_output("2", {...})
       └─ Send WebSocket event
   
   6g. Execute node 3 (agent):
       └─ Get inputs from parent
       └─ AgentModule.execute(config, inputs, context)
       └─ Call OpenAI API:
          - system_prompt: "You are helpful assistant"
          - user_content: "Summarize: Long text..."
       └─ Returns: {"response": "Summary...", "token_usage": {...}}
       └─ context.add_token_usage(...)
       └─ Send WebSocket event
   
   6h. Execute node 4 (output):
       └─ OutputModule.execute({}, inputs, context)
       └─ Returns: {"output": "Summary..."}
       └─ context.mark_as_final_output("4")
   
   6i. Success:
       └─ Save output_data to execution record
       └─ Save trace to MongoDB (all node logs)
       └─ Set status="completed"
       └─ Send WebSocket: {"type": "execution_completed"}

7. Frontend:
   └─ Receives WebSocket events
   └─ Updates canvas with node execution status
   └─ Shows real-time progress
   └─ On completion: Displays final output_data

8. User: Clicks "View Execution History"
   └─ Frontend sends GET /api/workspaces/{ws_id}/executions
   └─ Backend returns list of all executions
   └─ User selects execution to view trace details
   └─ Frontend retrieves trace from MongoDB
```

---

## Database Schema Diagram

```sql
TABLE users
├── id (PK, UUID)
├── email (UNIQUE)
├── hashed_password
├── name
├── avatar_url
├── created_at
└── updated_at

TABLE workspaces
├── id (PK, UUID)
├── name
├── owner_id (FK → users.id)
├── created_at
└── updated_at

TABLE workspace_members (Join table)
├── workspace_id (PK, FK → workspaces.id)
├── user_id (PK, FK → users.id)
└── role (owner, admin, editor, viewer)

TABLE workflows
├── id (PK, UUID)
├── workspace_id (FK → workspaces.id)
├── name
├── description
├── mongo_flow_id (→ MongoDB flows collection)
├── status (draft, published, archived)
├── version
├── created_by (FK → users.id)
├── created_at
├── updated_at
└── published_at

TABLE workflow_versions
├── id (PK, UUID)
├── workflow_id (FK → workflows.id)
├── version
├── mongo_flow_id (→ MongoDB for this version)
├── changelog
├── created_by (FK → users.id)
└── created_at

TABLE executions
├── id (PK, UUID)
├── workflow_id (FK → workflows.id, nullable)
├── workspace_id (FK → workspaces.id)
├── workflow_version
├── status (pending, running, completed, failed, cancelled)
├── trigger_type (manual, api, scheduled, webhook)
├── input_data (JSON)
├── output_data (JSON)
├── error_message
├── mongo_trace_id (→ MongoDB traces collection)
├── execution_time_ms
├── token_usage (JSON)
├── cost_usd
├── started_at
├── completed_at
└── created_at

TABLE knowledge_bases
├── id (PK, UUID)
├── workspace_id (FK → workspaces.id)
├── name
├── description
├── type (document, url, api)
├── config (JSON)
├── created_at
└── updated_at

TABLE documents
├── id (PK, UUID)
├── knowledge_base_id (FK → knowledge_bases.id)
├── filename
├── file_url
├── file_size
├── mime_type
├── content (TEXT)
├── metadata_ (JSON)
├── atlas_document_ids (JSON - MongoDB Atlas vector refs)
├── status (processing, indexed, failed)
├── created_at
└── updated_at

TABLE api_keys
├── id (PK, UUID)
├── workspace_id (FK → workspaces.id)
├── key_hash (UNIQUE)
├── name
├── created_at
└── expires_at

TABLE audit_logs
├── id (PK, UUID)
├── workspace_id (FK → workspaces.id)
├── user_id (FK → users.id)
├── action (created_workflow, executed_workflow, etc.)
├── resource_type (workflow, execution, etc.)
├── resource_id
├── details (JSON)
├── created_at
```

---

## MongoDB Collections

```javascript
// flows collection - stores workflow definitions
db.flows.insertOne({
    _id: ObjectId("..."),
    nodes: [
        { id: "1", type: "input", position: {x: 0, y: 0}, data: {} },
        { id: "2", type: "agent", position: {x: 100, y: 0}, data: {provider: "openai", model: "gpt-4o-mini"} },
        ...
    ],
    edges: [
        { id: "e1-2", source: "1", target: "2", sourceHandle: "output", targetHandle: "input" },
        ...
    ]
})

// traces collection - stores execution details
db.traces.insertOne({
    _id: ObjectId("..."),
    nodes: [
        {
            node_id: "1",
            node_type: "input",
            status: "completed",
            inputs: {},
            outputs: {output: "input_data"},
            duration_ms: 10,
            timestamp: "2024-01-01T00:00:00Z"
        },
        {
            node_id: "2",
            node_type: "agent",
            status: "completed",
            inputs: {input: "input_data"},
            outputs: {response: "AI response", token_usage: {}},
            duration_ms: 250,
            timestamp: "2024-01-01T00:00:00Z"
        },
        ...
    ]
})

// vectors collection - embeddings for RAG
db.vectors.insertOne({
    _id: ObjectId("..."),
    document_id: ObjectId("..."),
    content: "Document text chunk",
    embedding: [0.1, 0.2, ...],  // Vector embedding
    metadata: {source: "file.pdf", page: 1}
})
```

---

## Key Takeaways

1. **Hybrid Storage**: PostgreSQL for structured metadata + MongoDB for flexible JSON
2. **Async-First**: All I/O operations are non-blocking (FastAPI + SQLAlchemy async)
3. **Modular Execution**: Each node type is a pluggable module with the same interface
4. **Fault Tolerance**: Detailed trace logging + error recovery
5. **Real-Time Updates**: WebSocket + Redis pub/sub for live progress
6. **LLM Integration**: Seamless support for multiple AI providers (OpenAI, Anthropic, Gemini)
7. **RBAC**: Workspace-level permissions with roles
8. **Version Control**: Workflows have version history
9. **DAG Execution**: Topological sort ensures correct execution order

---

This walkthrough covers the complete backend architecture. Each component is designed to handle complex AI workflows while maintaining clean separation of concerns.
