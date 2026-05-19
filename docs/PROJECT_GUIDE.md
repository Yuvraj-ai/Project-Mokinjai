# Mokinjay AI Agent Builder - Comprehensive Project Guide

## Overview
Mokinjay is a visual AI agent builder platform where users create, configure, and run AI workflows by connecting modular components through a drag-and-drop interface. Think **"Zapier meets LangChain"** with a visual canvas.

### Core Concept
Users design AI workflows as Directed Acyclic Graphs (DAGs) where each node represents a functional module (Input, Agent LLM, Prompt, Transform, etc.) and edges represent data flow between nodes.

## Project Structure

```
mokinjay project/
├── backend/                 # Python/FastAPI backend
│   ├── app/                 # Main application code
│   │   ├── main.py          # FastAPI application entry point
│   │   ├── config.py        # Environment configuration
│   │   ├── database.py      # SQLAlchemy async engine setup
│   │   ├── models/          # Database models (User, Workspace, Workflow, Execution)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── routers/         # API route handlers
│   │   ├── engine/          # Core workflow execution engine
│   │   │   ├── dag_builder.py   # DAG construction, validation, topological sort
│   │   │   ├── executor.py      # Workflow execution engine
│   │   │   ├── context.py       # Execution context management
│   │   │   └── modules/         # Node type implementations
│   │   ├── middleware/        # Auth and RBAC middleware
│   │   ├── workers/           # Celery background task configuration
│   │   └── websocket/         # WebSocket handlers for real-time updates
│   ├── alembic/             # Database migrations
│   ├── requirements.txt     # Python dependencies
│   └── venv/                # Python virtual environment
├── frontend/                # React/TypeScript frontend
│   ├── src/
│   │   ├── api/             # Axios API client with JWT interceptors
│   │   ├── components/      # React components
│   │   │   ├── flow/        # Canvas, nodes, edges, toolbar
│   │   │   ├── execution/   # Execution monitoring components
│   │   │   ├── auth/        # Authentication components
│   │   │   ├── layout/      # Layout components
│   │   │   └── dashboard/   # Dashboard components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── store/           # Zustand state management
│   │   ├── pages/           # Page components
│   │   └── types/           # TypeScript interfaces
│   ├── package.json         # Frontend dependencies
│   └── vite.config.ts       # Vite configuration
├── docker/                  # Dockerfiles for services
├── docker-compose.yml       # Full stack orchestration
├── run_mokinjay.sh          # One-command startup script
├── .env.example             # Environment variable template
└── README.md                # Project overview
```

## Key Components

### Backend Architecture
1. **API Layer** (`app/routers/`)
   - Authentication routes (`/api/auth/*`)
   - Workspace management (`/api/workspaces/*`)
   - Workflow CRUD operations (`/api/workspaces/*/workflows/*`)
   - Execution triggering and monitoring (`/api/workspaces/*/executions/*`)
   - Knowledge base management (`/api/workspaces/*/knowledge-bases/*`)

2. **Execution Engine** (`app/engine/`)
   - `dag_builder.py`: Converts visual flow definitions to executable DAGs
   - `executor.py`: Main execution loop with conditional branching support
   - `context.py`: Tracks execution state, node outputs, and token usage
   - `modules/`: Implementation of each node type (Agent, Prompt, Transform, etc.)

3. **Data Layer**
   - SQLAlchemy ORM models with async support
   - Alembic for database migrations
   - Redis for Celery queue and WebSocket pub/sub
   - PostgreSQL for persistent storage

4. **Real-time Communication**
   - FastAPI WebSocket endpoints
   - Redis pub/sub for broadcasting execution updates
   - Frontend hook (`useWebSocket`) for live updates

### Frontend Architecture
1. **State Management**
   - Zustand stores for auth, workflow, and execution state
   - Custom hooks for API interactions and WebSocket connections

2. **Visual Flow Editor**
   - Built with React Flow library
   - Custom node types for each module (InputNode, AgentNode, etc.)
   - Properties panel for node configuration
   - Toolbar for workflow actions (save, run, etc.)

3. **User Interface**
   - Dashboard for listing workflows
   - Workflow editor canvas
   - Execution monitoring panel
   - Authentication flows (login/register)
   - Responsive design with TailwindCSS

## Module Types
The platform supports 8 core module types:

1. **Input** - Entry point for workflow data
2. **Prompt** - Template with `{{variable}}` substitution
3. **Agent** - LLM call (OpenAI/Anthropic providers)
4. **Output** - Collects final result
5. **Conditional** - Branch logic (contains, equals, regex, comparisons)
6. **Transform** - Data manipulation (JSON, text operations)
7. **HTTP Request** - External API calls
8. **Knowledge Base** - RAG-based document retrieval

## Data Flow
1. User creates workflow in visual editor
2. Workflow saved as JSON flow definition (nodes + edges)
3. On execution:
   - Backend loads workflow definition
   - DAG builder validates and topologically sorts nodes
   - Executor processes nodes in order
   - Data flows from parent nodes to children via ExecutionContext
   - Conditional nodes can skip subtrees based on evaluation
   - Full execution trace recorded for debugging

## Setup and Deployment

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 14+
- Redis 7+
- Docker (optional, for containerized setup)

### Quick Start
```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env to add your API keys:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...
#   JWT_SECRET_KEY=<generate-a-random-secret>

# 2. Run one-command startup
./run_mokinjay.sh
```

### Manual Setup
1. **Databases**: Start PostgreSQL and Redis
2. **Backend**: 
   - Create virtual environment
   - Install dependencies (`pip install -r requirements.txt`)
   - Run migrations (`alembic upgrade head`)
   - Start API server (`uvicorn app.main:app --reload`)
3. **Celery Worker**: Start in separate terminal
4. **Frontend**: Install npm packages and run dev server

### Docker Deployment
```bash
cp .env.example .env
# Edit .env with your API keys
docker-compose up --build
```

## Environment Variables
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Async PostgreSQL connection |
| `SYNC_DATABASE_URL` | Sync connection for Alembic |
| `REDIS_URL` | Redis connection |
| `JWT_SECRET_KEY` | JWT signing secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime |
| `OPENAI_API_KEY` | OpenAI API key for Agent nodes |
| `ANTHROPIC_API_KEY` | Anthropic API key for Agent nodes |

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register new user |
| `POST` | `/api/auth/login` | Login, returns JWT tokens |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `GET` | `/api/auth/me` | Get current user profile |
| `GET/POST` | `/api/workspaces` | List/create workspaces |
| `GET/POST` | `/api/workspaces/:id/workflows` | List/create workflows |
| `GET/PUT/DELETE` | `/api/workspaces/:id/workflows/:id` | Get/update/delete workflow |
| `POST` | `/api/workspaces/:id/workflows/:id/execute` | Execute workflow |
| `GET` | `/api/workspaces/:id/executions` | List executions |
| `GET` | `/api/workspaces/:id/executions/:id` | Get execution details + trace |
| `GET` | `/health` | Health check |
| `WS` | `/ws/executions/:id` | Real-time execution updates |

## Development Guidelines

### Backend
- Follow existing code patterns in `app/`
- Add new module types in `app/engine/modules/`
- Update `ModuleRegistry` when adding new modules
- Maintain async database operations
- Write unit tests for new functionality

### Frontend
- Follow existing component patterns in `src/components/`
- Add new node types in `src/components/flow/nodes/`
- Update node registry in flow components when adding nodes
- Use Zustand stores for state management
- Implement proper error boundaries

### Database
- Add new models in `app/models/`
- Create corresponding schemas in `app/schemas/`
- Generate migrations with `alembic revision --autogenerate`
- Follow existing model patterns

## Execution Process
1. User clicks "Run" on workflow
2. Frontend calls `/api/workspaces/:id/workflows/:id/execute`
3. Backend creates Execution record and enqueues Celery task
4. Celery worker executes workflow:
   - Loads workflow definition
   - Builds and validates DAG
   - Executes nodes in topological order
   - Handles conditional branching
   - Records full execution trace
   - Updates execution record with results
5. Frontend receives real-time updates via WebSocket
6. User views results in execution panel

## Extending the Platform

### Adding New Module Types
1. Create new module file in `backend/app/engine/modules/`
2. Implement `BaseModule` interface with `execute()` method
3. Register module in `backend/app/engine/modules/registry.py`
4. Create corresponding React component in `frontend/src/components/flow/nodes/`
5. Add node type to flow editor configuration

### Adding New API Endpoints
1. Create router file in `backend/app/routers/`
2. Implement endpoint functions with proper dependencies
3. Register router in `backend/app/main.py`
4. Add corresponding API service in `frontend/src/api/`
5. Create hooks/components as needed in frontend

## Troubleshooting

### Common Issues
1. **Database connection errors**
   - Verify PostgreSQL is running
   - Check `.env` DATABASE_URL format
   - Ensure migrations have been run

2. **Redis connection issues**
   - Verify Redis is running on port 6379
   - Check `.env` REDIS_URL format
   - Test with `redis-cli ping`

3. **LLM API failures**
   - Verify API keys in `.env`
   - Check provider-specific rate limits
   - Review execution trace for detailed errors

4. **WebSocket connection problems**
   - Verify backend is accessible
   - Check CORS settings in `main.py`
   - Ensure Redis pub/sub is working

### Debugging
- Check backend logs for detailed error messages
- Review execution trace in Execution History
- Use browser dev tools to inspect API calls
- Verify WebSocket connections in network tab

## License
This project is for personal/educational use.

## Contact
For questions or contributions, please refer to the project repository.