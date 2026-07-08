# Project Mokinjay — AI Agent Builder

A visual AI agent builder platform where users create, configure, and run AI workflows by connecting modular components through a drag-and-drop interface. Think **"Zapier meets LangChain"** with a visual canvas.

## What It Does

- **Visual Workflow Editor** — Drag-and-drop canvas powered by React Flow to design AI agent pipelines
- **8 Module Types** — Input, Agent (LLM), Prompt Template, Output, Conditional, Transform, HTTP Request, Knowledge Base
- **Multi-Provider LLM Support** — OpenAI, Anthropic, and Gemini models
- **Prompt Management System** — Create, edit, and reuse system prompts with auto-detected `{variables}`, token estimation, and linked references to Agent nodes
- **DAG Execution Engine** — Topological sorting, conditional branching, parallel-safe execution
- **Real-Time Updates** — WebSocket-based live execution progress on the canvas
- **Workspace & RBAC** — Multi-user workspaces with owner/admin/editor/viewer roles
- **Execution History** — Full trace logging with per-node inputs, outputs, timings, and token usage
- **Dark Mode** — Full dark theme with toggle, persisted to localStorage

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19, TypeScript, Vite 7, React Flow 12, Zustand, TanStack Query, Tailwind CSS 3 |
| **Backend** | Python, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic |
| **Database** | PostgreSQL 14+ (SQLite for development) |
| **Queue** | Celery + Redis 7+ |
| **Auth** | JWT (access + refresh tokens) |
| **LLM** | OpenAI SDK, Anthropic SDK, Google Gemini |
| **WebSocket** | FastAPI WebSocket + Redis pub/sub |

## Project Structure

```
mokinjay project/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Environment configuration
│   │   ├── database.py          # SQLAlchemy async engine
│   │   ├── models/              # Database models (User, Workspace, Workflow, Execution, PromptTemplate, etc.)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # API routes (auth, workspaces, workflows, executions, knowledge, prompts)
│   │   ├── engine/              # Workflow execution engine
│   │   │   ├── dag_builder.py   # Flow-to-DAG conversion, cycle detection, topological sort
│   │   │   ├── executor.py      # Main execution loop with conditional branching
│   │   │   ├── context.py       # Execution context (node outputs, trace, token tracking)
│   │   │   └── modules/         # Node type implementations (agent, prompt, transform, etc.)
│   │   ├── middleware/          # JWT auth + RBAC dependencies
│   │   ├── workers/             # Celery background tasks
│   │   ├── websocket/           # Real-time execution updates
│   │   └── utils/               # Security helpers, error classes
│   ├── alembic/                 # Database migrations
│   ├── requirements.txt
│   └── venv/
├── frontend/
│   ├── src/
│   │   ├── api/                 # Axios API client with JWT interceptors (workflows, prompts, etc.)
│   │   ├── components/
│   │   │   ├── flow/            # Canvas, custom nodes (8 types), edges, sidebar, toolbar
│   │   │   │   ├── nodes/       # BaseNode, AgentNode, PromptNode, InputNode, OutputNode, etc.
│   │   │   │   ├── edges/       # CustomEdge with animated connections
│   │   │   │   ├── sidebar/     # ModuleLibrary, PropertiesPanel, PromptLibrary, PromptCard, PromptEditor
│   │   │   │   └── toolbar/     # CanvasToolbar with Save, Run, zoom, workflow name
│   │   │   ├── execution/       # ExecutionPanel, ExecutionLog, ResultViewer
│   │   │   ├── auth/            # LoginForm, AdminOTPLogin, ProtectedRoute
│   │   │   ├── layout/          # AppLayout, Navbar (theme toggle), Sidebar (nav)
│   │   │   └── dashboard/       # WorkflowList, WorkflowCard (rename, delete)
│   │   ├── hooks/               # useAuth, useWorkflow, useExecution, useWebSocket
│   │   ├── store/               # Zustand stores (auth, workflow, execution, theme)
│   │   ├── pages/               # Login, Dashboard, WorkflowEditor, ExecutionHistory, Prompts
│   │   ├── types/               # TypeScript interfaces
│   │   └── lib/                 # Utilities, constants
│   ├── tailwind.config.js       # Tailwind v3 with custom theme (cream, ink, accent colors)
│   ├── package.json
│   └── vite.config.ts
├── docker/                      # Dockerfiles for backend & frontend
├── docker-compose.yml           # Full stack orchestration
├── run_mokinjay.sh              # One-command startup script
├── clear-cache.sh               # Clear Vite cache and restart
├── .env.example                 # Environment variable template
└── .gitignore
```

## Prerequisites

| Software | Version | Required For |
|----------|---------|-------------|
| Python | 3.12+ | Backend |
| Node.js | 20+ | Frontend |
| PostgreSQL | 14+ | Database |
| Redis | 7+ | Celery queue, WebSocket pub/sub |
| Docker | 20+ | Optional (can run Redis/Postgres via Docker) |

## Setup & Run

### Quick Start (One Command)

```bash
# 1. Clone the project and enter the directory
cd "mokinjay project"

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env to add your API keys:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...
#   JWT_SECRET_KEY=<generate-a-random-secret>

# 3. Run everything
./run_mokinjay.sh
```

The script will automatically:
- Start PostgreSQL and Redis (or use Docker for Redis)
- Create a Python virtual environment and install dependencies
- Run database migrations
- Install npm packages
- Start the backend, Celery worker, and frontend

Open **http://localhost:5173** in your browser.

### Manual Setup

#### 1. Start Databases

**Option A - Local install (Fedora/RHEL):**
```bash
sudo dnf install postgresql-server redis
sudo postgresql-setup --initdb
sudo systemctl start postgresql redis
sudo systemctl enable postgresql redis

# Set postgres password and create database
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo -u postgres createdb agentbuilder
```

**Option B - Docker:**
```bash
docker-compose up postgres redis -d
```

#### 2. Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000
```

#### 3. Celery Worker (separate terminal)

```bash
cd backend
source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

#### 4. Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

### Docker (Full Stack)

```bash
cp .env.example .env
# Edit .env with your API keys

docker-compose up --build
```

This starts all services: PostgreSQL, Redis, Backend (port 8000), Celery worker, Frontend (port 5173).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/agentbuilder` | Async PostgreSQL connection |
| `SYNC_DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/agentbuilder` | Sync connection (for Alembic) |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `JWT_SECRET_KEY` | `your-super-secret-key-change-in-production` | JWT signing secret (**change this**) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key for Agent nodes |
| `ANTHROPIC_API_KEY` | *(empty)* | Anthropic API key for Agent nodes |

## Usage

1. **Login** at http://localhost:5173/login (or use Admin OTP via Telegram)
2. **Create a workflow** from the dashboard by clicking "New Workflow"
3. **Build your pipeline** by dragging modules from the left sidebar onto the canvas:
   - **Input** — Entry point for your workflow data
   - **Prompt** — Template with `{variable}` substitution
   - **Agent** — LLM call (select provider: OpenAI, Anthropic, or Gemini)
   - **Output** — Collect the final result
   - **Conditional** — Branch logic (contains, equals, regex, greater/less than)
   - **Transform** — Data manipulation (JSON parse, extract field, uppercase, split, etc.)
   - **HTTP Request** — External API calls
   - **Knowledge Base** — RAG-based document retrieval
4. **Connect nodes** by dragging from output handles to input handles
5. **Configure nodes** by clicking them to open the properties panel
6. **Save** your workflow with the Save button
7. **Run** with the Run button and watch execution progress in real-time
8. **Rename workflows** by clicking the name in the toolbar or using the card menu
9. **Manage System Prompts** — Navigate to "System Prompts" in the sidebar to create, edit, and reuse prompts across workflows
10. **Toggle dark mode** using the sun/moon icon in the navbar

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Login, returns JWT tokens |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `GET` | `/api/auth/me` | Get current user profile |
| `POST` | `/api/auth/admin/otp/send` | Send OTP to Telegram |
| `POST` | `/api/auth/admin/otp/validate` | Validate OTP, return JWT |

### Workspaces
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/workspaces` | List/create workspaces |
| `GET/PUT/DELETE` | `/api/workspaces/:id` | Get/update/delete workspace |

### Workflows
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/workspaces/:id/workflows` | List/create workflows |
| `GET/PUT/DELETE` | `/api/workspaces/:id/workflows/:id` | Get/update/delete workflow |
| `POST` | `/api/workspaces/:id/workflows/:id/execute` | Execute a workflow |
| `POST` | `/api/workspaces/:id/workflows/:id/publish` | Publish workflow |

### Prompts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/workspaces/:id/prompts` | List/create system prompts |
| `GET/PUT/DELETE` | `/api/workspaces/:id/prompts/:id` | Get/update/delete prompt |

### Executions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/workspaces/:id/executions` | List executions |
| `GET` | `/api/workspaces/:id/executions/:id` | Get execution details + trace |
| `POST` | `/api/workspaces/:id/executions/:id/cancel` | Cancel running execution |

### Knowledge Base
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/workspaces/:id/knowledge-bases` | List/create knowledge bases |
| `GET/DELETE` | `/api/workspaces/:id/knowledge-bases/:id` | Get/delete knowledge base |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `WS` | `/ws/executions/:id` | Real-time execution updates |

## Architecture

```
Browser (React 19 + React Flow)
    │
    ├── REST API ──────► FastAPI (uvicorn)
    │                        │
    │                        ├── SQLAlchemy ──► PostgreSQL
    │                        │
    │                        ├── Celery task dispatch ──► Redis ──► Celery Worker
    │                        │                                         │
    │                        │                           WorkflowExecutor
    │                        │                           (DAG build → topological sort
    │                        │                            → module execution → trace)
    │                        │
    └── WebSocket ◄──────────┤◄── Redis pub/sub ◄──────────────────────┘
         (live node status)
```

## License

This project is for personal/educational use.

---

Based on Project TKAE (To Kill An Eagle).
