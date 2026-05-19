# AI Agent Builder - Production Implementation Plan

## Executive Summary

Build a production-ready visual AI agent builder platform where users can create, configure, and deploy AI agents by connecting modular components through a drag-and-drop interface. Think "Zapier meets LangChain" with a visual canvas.

**Core Value Proposition**: No-code AI workflow builder for creating sophisticated AI agents without writing code.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [System Architecture](#system-architecture)
3. [Database Schema](#database-schema)
4. [Project Structure](#project-structure)
5. [Core Features & Modules](#core-features--modules)
6. [Implementation Phases](#implementation-phases)
7. [API Specifications](#api-specifications)
8. [Security & Authentication](#security--authentication)
9. [Testing Strategy](#testing-strategy)
10. [Deployment & DevOps](#deployment--devops)
11. [Monitoring & Observability](#monitoring--observability)
12. [Success Metrics](#success-metrics)

---

## Tech Stack

### Frontend
```yaml
Framework: Next.js 14+ (App Router)
Language: TypeScript
UI Components: shadcn/ui + Radix UI
Styling: TailwindCSS
State Management: Zustand
Flow Editor: React Flow
Forms: React Hook Form + Zod
Code Editor: Monaco Editor (VSCode editor)
HTTP Client: TanStack Query (React Query)
WebSocket: Socket.IO Client
Icons: Lucide React
```

**Justification**:
- Next.js: SSR, API routes, file-based routing, excellent DX
- React Flow: Industry standard for node-based UIs
- Zustand: Lightweight, less boilerplate than Redux
- shadcn/ui: Customizable, accessible, copy-paste components

### Backend
```yaml
Framework: Node.js + Express.js
Language: TypeScript
Validation: Zod
ORM: Prisma
Job Queue: BullMQ + Redis
WebSocket: Socket.IO
Authentication: Clerk or NextAuth.js
File Storage: AWS S3 or Cloudflare R2
```

**Justification**:
- Express: Battle-tested, extensive middleware ecosystem
- Prisma: Type-safe ORM, excellent migrations
- BullMQ: Robust job processing with Redis backing
- Clerk: Complete auth solution with user management

### Database
```yaml
Primary: PostgreSQL 14+
Cache: Redis 7+
Vector Store: Pinecone or Qdrant
Search: PostgreSQL Full-Text Search (initial) → ElasticSearch (scale)
```

### AI/LLM
```yaml
Orchestration: LangChain.js
LLM Providers: 
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic (Claude)
  - Google (Gemini)
Embeddings: OpenAI text-embedding-3-small
Vector DB: Pinecone (managed) or Qdrant (self-hosted)
```

### DevOps & Infrastructure
```yaml
Container: Docker + Docker Compose
CI/CD: GitHub Actions
Hosting: 
  - Frontend: Vercel
  - Backend: Railway or AWS ECS
  - Database: Supabase or AWS RDS
Monitoring: Sentry + PostHog + Prometheus
Logging: Winston + Loki
```

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                    CLIENT LAYER                      │
├─────────────────────────────────────────────────────┤
│  Next.js App (SSR)                                  │
│  ├── Flow Canvas (React Flow)                       │
│  ├── Module Configuration Panel                     │
│  ├── Execution Dashboard                            │
│  └── Real-time Updates (Socket.IO)                  │
└──────────────────┬──────────────────────────────────┘
                   │ HTTPS/WSS
┌──────────────────▼──────────────────────────────────┐
│                 API GATEWAY LAYER                    │
├─────────────────────────────────────────────────────┤
│  Express.js API Server                              │
│  ├── REST API Endpoints                             │
│  ├── WebSocket Server                               │
│  ├── Authentication Middleware                      │
│  └── Rate Limiting & Validation                     │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┬──────────────┐
        │                     │              │
┌───────▼────────┐  ┌────────▼─────┐  ┌────▼──────┐
│   PostgreSQL   │  │     Redis    │  │  Pinecone │
│   (Metadata)   │  │  (Cache/Jobs)│  │ (Vectors) │
└────────────────┘  └──────┬───────┘  └───────────┘
                           │
                  ┌────────▼─────────┐
                  │  Worker Processes │
                  ├──────────────────┤
                  │ Workflow Executor │
                  │ LLM Orchestrator  │
                  │ Document Processor│
                  └──────────────────┘
```

### Component Diagram

```
Frontend Components:
├── Canvas (Flow Editor)
│   ├── Node Renderer (Custom nodes)
│   ├── Edge Renderer (Connections)
│   ├── Mini-map
│   └── Controls (Zoom, Pan)
├── Sidebar
│   ├── Module Library
│   ├── Properties Panel
│   └── Execution Logs
└── Navbar
    ├── Save/Deploy
    ├── Test Run
    └── User Menu

Backend Services:
├── API Service (Express)
│   ├── Workflow CRUD
│   ├── Execution Endpoints
│   └── Real-time Events
├── Execution Engine
│   ├── DAG Builder
│   ├── Topological Sorter
│   ├── Node Executor
│   └── Context Manager
├── Module Registry
│   ├── Agent Modules
│   ├── Knowledge Modules
│   ├── Tool Modules
│   └── Logic Modules
└── Worker Service (BullMQ)
    ├── Job Processor
    ├── Retry Logic
    └── Result Aggregator
```

---

## Database Schema

### PostgreSQL Schema

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (if not using Clerk)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Workspaces (multi-tenancy)
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Workspace members
CREATE TABLE workspace_members (
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- owner, admin, editor, viewer
    PRIMARY KEY (workspace_id, user_id)
);

-- Workflows
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    flow_definition JSONB NOT NULL, -- Nodes, edges, positions
    status VARCHAR(50) DEFAULT 'draft', -- draft, published, archived
    version INTEGER DEFAULT 1,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP
);

-- Workflow versions (for version control)
CREATE TABLE workflow_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    flow_definition JSONB NOT NULL,
    changelog TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(workflow_id, version)
);

-- Executions
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE SET NULL,
    workflow_version INTEGER,
    status VARCHAR(50) NOT NULL, -- pending, running, completed, failed, cancelled
    trigger_type VARCHAR(50), -- manual, api, scheduled, webhook
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    execution_trace JSONB, -- Step-by-step execution log
    execution_time_ms INTEGER,
    token_usage JSONB, -- {prompt_tokens, completion_tokens, total_tokens}
    cost_usd DECIMAL(10, 6),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Knowledge bases
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50), -- document, url, api
    config JSONB, -- Vector DB config, chunking strategy
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Documents in knowledge bases
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_base_id UUID REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    filename VARCHAR(255),
    file_url TEXT,
    file_size INTEGER,
    mime_type VARCHAR(100),
    content TEXT,
    metadata JSONB,
    vector_ids TEXT[], -- IDs in vector database
    status VARCHAR(50), -- processing, indexed, failed
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- API Keys (for programmatic access)
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) UNIQUE NOT NULL, -- Hashed API key
    prefix VARCHAR(20) NOT NULL, -- For display (e.g., "sk-abc...")
    last_used_at TIMESTAMP,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Audit logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    metadata JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_workflows_workspace ON workflows(workspace_id);
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_executions_workflow ON executions(workflow_id);
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_created ON executions(created_at DESC);
CREATE INDEX idx_documents_kb ON documents(knowledge_base_id);
CREATE INDEX idx_audit_logs_workspace ON audit_logs(workspace_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- Full-text search on workflows
CREATE INDEX idx_workflows_search ON workflows USING GIN (to_tsvector('english', name || ' ' || COALESCE(description, '')));
```

### Prisma Schema

```prisma
// prisma/schema.prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(uuid())
  email     String   @unique
  name      String?
  avatarUrl String?  @map("avatar_url")
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  ownedWorkspaces  Workspace[]
  workspaceMembers WorkspaceMember[]
  workflows        Workflow[]
  apiKeys          ApiKey[]
  auditLogs        AuditLog[]

  @@map("users")
}

model Workspace {
  id        String   @id @default(uuid())
  name      String
  ownerId   String   @map("owner_id")
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  owner           User              @relation(fields: [ownerId], references: [id], onDelete: Cascade)
  members         WorkspaceMember[]
  workflows       Workflow[]
  knowledgeBases  KnowledgeBase[]
  apiKeys         ApiKey[]
  auditLogs       AuditLog[]

  @@map("workspaces")
}

model WorkspaceMember {
  workspaceId String @map("workspace_id")
  userId      String @map("user_id")
  role        String

  workspace Workspace @relation(fields: [workspaceId], references: [id], onDelete: Cascade)
  user      User      @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@id([workspaceId, userId])
  @@map("workspace_members")
}

model Workflow {
  id             String   @id @default(uuid())
  workspaceId    String   @map("workspace_id")
  name           String
  description    String?
  flowDefinition Json     @map("flow_definition")
  status         String   @default("draft")
  version        Int      @default(1)
  createdBy      String   @map("created_by")
  createdAt      DateTime @default(now()) @map("created_at")
  updatedAt      DateTime @updatedAt @map("updated_at")
  publishedAt    DateTime? @map("published_at")

  workspace Workspace           @relation(fields: [workspaceId], references: [id], onDelete: Cascade)
  creator   User                @relation(fields: [createdBy], references: [id])
  versions  WorkflowVersion[]
  executions Execution[]

  @@map("workflows")
}

model WorkflowVersion {
  id             String   @id @default(uuid())
  workflowId     String   @map("workflow_id")
  version        Int
  flowDefinition Json     @map("flow_definition")
  changelog      String?
  createdBy      String   @map("created_by")
  createdAt      DateTime @default(now()) @map("created_at")

  workflow Workflow @relation(fields: [workflowId], references: [id], onDelete: Cascade)

  @@unique([workflowId, version])
  @@map("workflow_versions")
}

model Execution {
  id                String    @id @default(uuid())
  workflowId        String?   @map("workflow_id")
  workflowVersion   Int?      @map("workflow_version")
  status            String
  triggerType       String?   @map("trigger_type")
  inputData         Json?     @map("input_data")
  outputData        Json?     @map("output_data")
  errorMessage      String?   @map("error_message")
  executionTrace    Json?     @map("execution_trace")
  executionTimeMs   Int?      @map("execution_time_ms")
  tokenUsage        Json?     @map("token_usage")
  costUsd           Decimal?  @map("cost_usd") @db.Decimal(10, 6)
  startedAt         DateTime? @map("started_at")
  completedAt       DateTime? @map("completed_at")
  createdAt         DateTime  @default(now()) @map("created_at")

  workflow Workflow? @relation(fields: [workflowId], references: [id], onDelete: SetNull)

  @@map("executions")
}

model KnowledgeBase {
  id          String   @id @default(uuid())
  workspaceId String   @map("workspace_id")
  name        String
  description String?
  type        String
  config      Json
  createdAt   DateTime @default(now()) @map("created_at")
  updatedAt   DateTime @updatedAt @map("updated_at")

  workspace Workspace   @relation(fields: [workspaceId], references: [id], onDelete: Cascade)
  documents Document[]

  @@map("knowledge_bases")
}

model Document {
  id               String    @id @default(uuid())
  knowledgeBaseId  String    @map("knowledge_base_id")
  filename         String?
  fileUrl          String?   @map("file_url")
  fileSize         Int?      @map("file_size")
  mimeType         String?   @map("mime_type")
  content          String?
  metadata         Json?
  vectorIds        String[]  @map("vector_ids")
  status           String
  createdAt        DateTime  @default(now()) @map("created_at")
  updatedAt        DateTime  @updatedAt @map("updated_at")

  knowledgeBase KnowledgeBase @relation(fields: [knowledgeBaseId], references: [id], onDelete: Cascade)

  @@map("documents")
}

model ApiKey {
  id          String    @id @default(uuid())
  workspaceId String    @map("workspace_id")
  name        String
  keyHash     String    @unique @map("key_hash")
  prefix      String
  lastUsedAt  DateTime? @map("last_used_at")
  createdBy   String    @map("created_by")
  createdAt   DateTime  @default(now()) @map("created_at")
  expiresAt   DateTime? @map("expires_at")

  workspace Workspace @relation(fields: [workspaceId], references: [id], onDelete: Cascade)
  creator   User      @relation(fields: [createdBy], references: [id])

  @@map("api_keys")
}

model AuditLog {
  id           String   @id @default(uuid())
  workspaceId  String   @map("workspace_id")
  userId       String?  @map("user_id")
  action       String
  resourceType String?  @map("resource_type")
  resourceId   String?  @map("resource_id")
  metadata     Json?
  ipAddress    String?  @map("ip_address")
  userAgent    String?  @map("user_agent")
  createdAt    DateTime @default(now()) @map("created_at")

  workspace Workspace @relation(fields: [workspaceId], references: [id], onDelete: Cascade)
  user      User?     @relation(fields: [userId], references: [id], onDelete: SetNull)

  @@map("audit_logs")
}
```

---

## Project Structure

```
ai-agent-builder/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
├── apps/
│   ├── web/                      # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/              # App router
│   │   │   │   ├── (auth)/       # Auth routes
│   │   │   │   ├── (dashboard)/  # Main app
│   │   │   │   │   ├── workflows/
│   │   │   │   │   │   ├── [id]/
│   │   │   │   │   │   │   ├── edit/
│   │   │   │   │   │   │   └── page.tsx
│   │   │   │   │   │   └── page.tsx
│   │   │   │   │   ├── knowledge/
│   │   │   │   │   ├── executions/
│   │   │   │   │   └── settings/
│   │   │   │   ├── api/          # API routes
│   │   │   │   │   └── trpc/
│   │   │   │   └── layout.tsx
│   │   │   ├── components/
│   │   │   │   ├── flow/
│   │   │   │   │   ├── Canvas.tsx
│   │   │   │   │   ├── nodes/
│   │   │   │   │   │   ├── BaseNode.tsx
│   │   │   │   │   │   ├── AgentNode.tsx
│   │   │   │   │   │   ├── KnowledgeNode.tsx
│   │   │   │   │   │   └── ...
│   │   │   │   │   ├── edges/
│   │   │   │   │   └── sidebar/
│   │   │   │   ├── ui/           # shadcn components
│   │   │   │   └── ...
│   │   │   ├── lib/
│   │   │   │   ├── trpc.ts
│   │   │   │   ├── utils.ts
│   │   │   │   └── validations.ts
│   │   │   ├── hooks/
│   │   │   │   ├── useWorkflow.ts
│   │   │   │   └── useExecution.ts
│   │   │   ├── store/
│   │   │   │   ├── workflowStore.ts
│   │   │   │   └── executionStore.ts
│   │   │   └── types/
│   │   │       ├── nodes.ts
│   │   │       └── workflow.ts
│   │   ├── public/
│   │   ├── package.json
│   │   └── next.config.js
│   └── api/                      # Backend API
│       ├── src/
│       │   ├── server.ts
│       │   ├── app.ts
│       │   ├── config/
│       │   │   ├── database.ts
│       │   │   ├── redis.ts
│       │   │   └── env.ts
│       │   ├── middleware/
│       │   │   ├── auth.ts
│       │   │   ├── errorHandler.ts
│       │   │   ├── rateLimit.ts
│       │   │   └── validation.ts
│       │   ├── routes/
│       │   │   ├── workflows.ts
│       │   │   ├── executions.ts
│       │   │   ├── knowledge.ts
│       │   │   └── webhooks.ts
│       │   ├── services/
│       │   │   ├── workflow/
│       │   │   │   ├── WorkflowService.ts
│       │   │   │   ├── ExecutionEngine.ts
│       │   │   │   ├── DAGBuilder.ts
│       │   │   │   └── ContextManager.ts
│       │   │   ├── modules/
│       │   │   │   ├── BaseModule.ts
│       │   │   │   ├── AgentModule.ts
│       │   │   │   ├── KnowledgeModule.ts
│       │   │   │   ├── ToolModule.ts
│       │   │   │   └── ModuleRegistry.ts
│       │   │   ├── llm/
│       │   │   │   ├── LLMProvider.ts
│       │   │   │   ├── OpenAIProvider.ts
│       │   │   │   ├── AnthropicProvider.ts
│       │   │   │   └── TokenCounter.ts
│       │   │   ├── vectordb/
│       │   │   │   ├── VectorDBService.ts
│       │   │   │   └── EmbeddingService.ts
│       │   │   └── storage/
│       │   │       ├── S3Service.ts
│       │   │       └── DocumentProcessor.ts
│       │   ├── workers/
│       │   │   ├── execution.worker.ts
│       │   │   ├── document.worker.ts
│       │   │   └── queue.ts
│       │   ├── websocket/
│       │   │   └── executionSocket.ts
│       │   ├── utils/
│       │   │   ├── crypto.ts
│       │   │   ├── logger.ts
│       │   │   └── errors.ts
│       │   └── types/
│       │       ├── workflow.types.ts
│       │       └── execution.types.ts
│       ├── prisma/
│       │   ├── schema.prisma
│       │   └── migrations/
│       ├── tests/
│       │   ├── unit/
│       │   ├── integration/
│       │   └── e2e/
│       ├── package.json
│       └── tsconfig.json
├── packages/
│   ├── shared/                   # Shared types & utils
│   │   ├── src/
│   │   │   ├── types/
│   │   │   └── utils/
│   │   └── package.json
│   └── config/                   # Shared configs
│       ├── eslint-config/
│       └── typescript-config/
├── docker/
│   ├── Dockerfile.web
│   ├── Dockerfile.api
│   └── Dockerfile.worker
├── docker-compose.yml
├── .env.example
├── .gitignore
├── package.json                  # Root package.json (workspace)
├── pnpm-workspace.yaml
├── turbo.json
└── README.md
```

---

## Core Features & Modules

### Module Types & Specifications

#### 1. Agent Module

**Purpose**: Execute LLM calls with configured system prompts and parameters.

**Configuration**:
```typescript
interface AgentModuleConfig {
  provider: 'openai' | 'anthropic' | 'google';
  model: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  topP?: number;
  frequencyPenalty?: number;
  presencePenalty?: number;
  stopSequences?: string[];
}
```

**Inputs**:
- `input` (string): User message or prompt
- `context` (object): Additional context data

**Outputs**:
- `response` (string): LLM response
- `tokenUsage` (object): Token counts and cost

**Implementation Notes**:
- Support streaming responses
- Implement retry logic with exponential backoff
- Track token usage for billing
- Cache responses when appropriate

---

#### 2. Knowledge Base Module

**Purpose**: Retrieve relevant documents from vector database.

**Configuration**:
```typescript
interface KnowledgeModuleConfig {
  knowledgeBaseId: string;
  topK: number;
  similarityThreshold: number;
  rerankEnabled: boolean;
  chunkSize?: number;
}
```

**Inputs**:
- `query` (string): Search query
- `filters` (object): Metadata filters

**Outputs**:
- `documents` (array): Retrieved documents
- `context` (string): Concatenated document text
- `scores` (array): Similarity scores

**Implementation Notes**:
- Generate embeddings for queries
- Support metadata filtering
- Implement reranking for better results
- Cache frequently accessed documents

---

#### 3. Prompt Template Module

**Purpose**: Format prompts with variables.

**Configuration**:
```typescript
interface PromptModuleConfig {
  template: string;
  variables: string[];
  outputFormat?: 'text' | 'json';
}
```

**Inputs**:
- Dynamic inputs based on variables

**Outputs**:
- `prompt` (string): Formatted prompt

**Implementation Notes**:
- Support Handlebars-style templates: `{{variable}}`
- Handle missing variables gracefully
- Validate JSON output if specified

---

#### 4. Conditional Module

**Purpose**: Branch execution based on conditions.

**Configuration**:
```typescript
interface ConditionalModuleConfig {
  condition: {
    type: 'contains' | 'equals' | 'regex' | 'javascript' | 'ai';
    value: string;
    operator?: 'and' | 'or';
  };
}
```

**Inputs**:
- `input` (any): Data to evaluate

**Outputs**:
- `branch` (string): 'true' or 'false'
- `data` (any): Pass-through data

**Implementation Notes**:
- Sandbox JavaScript execution
- For AI conditions, use LLM to evaluate
- Support complex boolean logic

---

#### 5. Transform Module

**Purpose**: Transform data between formats.

**Configuration**:
```typescript
interface TransformModuleConfig {
  transformation: 'json-parse' | 'json-stringify' | 'extract-field' | 'custom';
  script?: string; // For custom transformations
}
```

**Inputs**:
- `input` (any)

**Outputs**:
- `output` (any)

---

#### 6. HTTP Request Module

**Purpose**: Make external API calls.

**Configuration**:
```typescript
interface HTTPModuleConfig {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  url: string;
  headers: Record<string, string>;
  body?: any;
  timeout?: number;
}
```

---

#### 7. Loop Module

**Purpose**: Iterate over arrays.

**Configuration**:
```typescript
interface LoopModuleConfig {
  maxIterations: number;
  parallelExecution: boolean;
}
```

---

#### 8. Code Execution Module

**Purpose**: Run custom JavaScript/Python code.

**Configuration**:
```typescript
interface CodeModuleConfig {
  language: 'javascript' | 'python';
  code: string;
  timeout: number;
  allowedPackages: string[];
}
```

**Implementation Notes**:
- Use VM2 for JavaScript sandboxing
- Use Docker containers for Python
- Strict resource limits (CPU, memory, time)

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal**: Setup infrastructure and basic workflow CRUD.

**Tasks**:
1. **Project Setup**
   - Initialize monorepo with Turborepo
   - Setup Next.js app
   - Setup Express API
   - Configure Prisma with PostgreSQL
   - Setup Docker Compose for local development

2. **Authentication**
   - Integrate Clerk or NextAuth.js
   - Implement workspace creation
   - Setup RBAC middleware

3. **Basic Backend**
   - Workflow CRUD endpoints
   - Database models and migrations
   - Basic validation with Zod

4. **Basic Frontend**
   - Dashboard layout
   - Workflow list view
   - Basic navigation

**Deliverable**: User can sign up, create workspace, and create empty workflows.

---

### Phase 2: Flow Editor (Week 3-4)

**Goal**: Build visual workflow editor.

**Tasks**:
1. **React Flow Integration**
   - Setup canvas component
   - Implement drag-and-drop from module library
   - Node positioning and connections
   - Custom node styling

2. **Module Library**
   - Create base node component
   - Implement 3-5 core modules (Agent, Knowledge, Prompt, Output)
   - Configuration panel for each module
   - Validation for node configurations

3. **Flow Persistence**
   - Save flow definition to database
   - Load flow from database
   - Auto-save functionality
   - Version tracking

4. **UI Polish**
   - Mini-map
   - Zoom controls
   - Node search
   - Keyboard shortcuts

**Deliverable**: User can visually create workflows by connecting modules.

---

### Phase 3: Execution Engine (Week 5-6)

**Goal**: Execute workflows.

**Tasks**:
1. **DAG Builder**
   - Convert React Flow data to execution graph
   - Topological sorting
   - Cycle detection
   - Validation

2. **Execution Engine**
   - Context management
   - Node executor factory
   - Error handling and rollback
   - Execution tracing

3. **Module Implementations**
   - Agent module with OpenAI integration
   - Prompt template module
   - Output module
   - Basic testing for each

4. **Execution UI**
   - "Run" button
   - Execution status display
   - Real-time node highlighting
   - Results viewer

**Deliverable**: User can execute simple workflows with Agent + Prompt.

---

### Phase 4: Advanced Modules (Week 7-8)

**Goal**: Add knowledge bases and advanced modules.

**Tasks**:
1. **Knowledge Base**
   - Document upload UI
   - Document processing (chunking, embedding)
   - Vector DB integration (Pinecone)
   - Knowledge module implementation

2. **Additional Modules**
   - Conditional module
   - Loop module
   - HTTP request module
   - Transform module

3. **Worker Queue**
   - Setup BullMQ
   - Move long executions to queue
   - Job monitoring
   - Retry logic

4. **Real-time Updates**
   - Socket.IO integration
   - Stream execution events
   - Live node status updates
   - Progress indicators

**Deliverable**: User can create RAG workflows with knowledge bases.

---

### Phase 5: Production Features (Week 9-10)

**Goal**: Production-ready features.

**Tasks**:
1. **API Access**
   - Generate API keys
   - REST API for workflow execution
   - Webhook triggers
   - Rate limiting

2. **Monitoring & Logging**
   - Execution history
   - Token usage tracking
   - Cost calculation
   - Error logs

3. **Optimization**
   - Response caching
   - Parallel execution where possible
   - Database query optimization
   - Frontend performance

4. **Security Hardening**
   - Input sanitization
   - Rate limiting
   - API key rotation
   - Audit logging

**Deliverable**: Production-ready platform with API access.

---

### Phase 6: Scale & Polish (Week 11-12)

**Goal**: Scale and user experience.

**Tasks**:
1. **Templates & Marketplace**
   - Pre-built workflow templates
   - Template import/export
   - Community sharing

2. **Collaboration**
   - Team workspaces
   - Shared workflows
   - Comments on nodes

3. **Testing & Documentation**
   - Comprehensive test coverage
   - API documentation
   - User guides
   - Video tutorials

4. **Deployment**
   - CI/CD pipeline
   - Production deployment
   - Monitoring setup
   - Backup strategy

**Deliverable**: Fully launched product.

---

## API Specifications

### REST API Endpoints

#### Workflows

```typescript
// Create workflow
POST /api/v1/workspaces/:workspaceId/workflows
Body: {
  name: string;
  description?: string;
  flowDefinition: object;
}
Response: Workflow

// Get workflow
GET /api/v1/workspaces/:workspaceId/workflows/:id
Response: Workflow

// Update workflow
PUT /api/v1/workspaces/:workspaceId/workflows/:id
Body: Partial<Workflow>
Response: Workflow

// Delete workflow
DELETE /api/v1/workspaces/:workspaceId/workflows/:id
Response: { success: boolean }

// List workflows
GET /api/v1/workspaces/:workspaceId/workflows
Query: {
  page?: number;
  limit?: number;
  status?: string;
  search?: string;
}
Response: { workflows: Workflow[], total: number }

// Publish workflow
POST /api/v1/workspaces/:workspaceId/workflows/:id/publish
Response: Workflow
```

#### Executions

```typescript
// Execute workflow
POST /api/v1/workspaces/:workspaceId/workflows/:id/execute
Body: {
  input: any;
  async?: boolean; // Execute in background
}
Response: Execution | { executionId: string }

// Get execution
GET /api/v1/workspaces/:workspaceId/executions/:id
Response: Execution

// List executions
GET /api/v1/workspaces/:workspaceId/executions
Query: {
  workflowId?: string;
  status?: string;
  page?: number;
  limit?: number;
}
Response: { executions: Execution[], total: number }

// Cancel execution
POST /api/v1/workspaces/:workspaceId/executions/:id/cancel
Response: { success: boolean }

// Get execution logs
GET /api/v1/workspaces/:workspaceId/executions/:id/logs
Response: { logs: Array<LogEntry> }
```

#### Knowledge Bases

```typescript
// Create knowledge base
POST /api/v1/workspaces/:workspaceId/knowledge-bases
Body: {
  name: string;
  description?: string;
  type: string;
  config: object;
}
Response: KnowledgeBase

// Upload document
POST /api/v1/workspaces/:workspaceId/knowledge-bases/:id/documents
Content-Type: multipart/form-data
Body: {
  file: File;
  metadata?: object;
}
Response: Document

// Search knowledge base
POST /api/v1/workspaces/:workspaceId/knowledge-bases/:id/search
Body: {
  query: string;
  topK?: number;
  filters?: object;
}
Response: { documents: Document[], scores: number[] }
```

### WebSocket Events

```typescript
// Client → Server
socket.emit('subscribe_execution', { executionId: string });
socket.emit('unsubscribe_execution', { executionId: string });

// Server → Client
socket.on('execution_started', { executionId: string });
socket.on('node_started', { executionId: string, nodeId: string });
socket.on('node_completed', { 
  executionId: string, 
  nodeId: string, 
  output: any 
});
socket.on('node_failed', { 
  executionId: string, 
  nodeId: string, 
  error: string 
});
socket.on('execution_completed', { 
  executionId: string, 
  output: any 
});
socket.on('execution_failed', { 
  executionId: string, 
  error: string 
});
```

---

## Security & Authentication

### Authentication Strategy

**Recommended**: Clerk (simplest, best DX)

```typescript
// Middleware to protect routes
import { authMiddleware } from '@clerk/nextjs';

export default authMiddleware({
  publicRoutes: ['/api/webhooks/(.*)'],
});

// Backend API verification
import { ClerkExpressWithAuth } from '@clerk/clerk-sdk-node';

app.use(ClerkExpressWithAuth());

app.get('/api/protected', (req, res) => {
  const userId = req.auth.userId;
  // ...
});
```

### Authorization

**RBAC Model**:
- **Owner**: Full access, billing
- **Admin**: Manage members, workflows
- **Editor**: Create/edit workflows
- **Viewer**: View only

```typescript
// Middleware
async function checkPermission(
  req: Request,
  res: Response,
  next: NextFunction
) {
  const { workspaceId } = req.params;
  const userId = req.auth.userId;
  
  const member = await prisma.workspaceMember.findUnique({
    where: {
      workspaceId_userId: { workspaceId, userId }
    }
  });
  
  if (!member || !hasPermission(member.role, req.method)) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  
  next();
}
```

### API Key Authentication

```typescript
// Generate API key
function generateApiKey(): { key: string, hash: string, prefix: string } {
  const key = `sk_${crypto.randomBytes(32).toString('hex')}`;
  const hash = crypto.createHash('sha256').update(key).digest('hex');
  const prefix = key.substring(0, 10);
  
  return { key, hash, prefix };
}

// Middleware
async function authenticateApiKey(
  req: Request,
  res: Response,
  next: NextFunction
) {
  const apiKey = req.headers['x-api-key'];
  
  if (!apiKey) {
    return res.status(401).json({ error: 'API key required' });
  }
  
  const hash = crypto.createHash('sha256').update(apiKey).digest('hex');
  
  const key = await prisma.apiKey.findUnique({
    where: { keyHash: hash },
    include: { workspace: true }
  });
  
  if (!key || (key.expiresAt && key.expiresAt < new Date())) {
    return res.status(401).json({ error: 'Invalid API key' });
  }
  
  // Update last used
  await prisma.apiKey.update({
    where: { id: key.id },
    data: { lastUsedAt: new Date() }
  });
  
  req.workspace = key.workspace;
  next();
}
```

### Input Validation

```typescript
import { z } from 'zod';

// Workflow schema
const workflowSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().max(1000).optional(),
  flowDefinition: z.object({
    nodes: z.array(z.object({
      id: z.string(),
      type: z.string(),
      data: z.record(z.any()),
      position: z.object({
        x: z.number(),
        y: z.number()
      })
    })),
    edges: z.array(z.object({
      id: z.string(),
      source: z.string(),
      target: z.string(),
      sourceHandle: z.string().optional(),
      targetHandle: z.string().optional()
    }))
  })
});

// Middleware
function validateBody(schema: z.ZodSchema) {
  return (req: Request, res: Response, next: NextFunction) => {
    try {
      req.body = schema.parse(req.body);
      next();
    } catch (error) {
      res.status(400).json({ 
        error: 'Validation failed', 
        details: error.errors 
      });
    }
  };
}
```

### Rate Limiting

```typescript
import rateLimit from 'express-rate-limit';
import RedisStore from 'rate-limit-redis';

const limiter = rateLimit({
  store: new RedisStore({
    client: redis,
    prefix: 'rl:'
  }),
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Per IP
  message: 'Too many requests',
  standardHeaders: true,
  legacyHeaders: false
});

// Different limits for different endpoints
const executionLimiter = rateLimit({
  store: new RedisStore({ client: redis }),
  windowMs: 60 * 1000, // 1 minute
  max: 10, // 10 executions per minute
  keyGenerator: (req) => req.workspace.id // Per workspace
});

app.use('/api/', limiter);
app.post('/api/*/execute', executionLimiter);
```

---

## Testing Strategy

### Unit Tests

**Tools**: Jest, Testing Library

```typescript
// Example: DAG Builder test
describe('DAGBuilder', () => {
  it('should sort nodes topologically', () => {
    const flow = {
      nodes: [
        { id: 'a', type: 'input' },
        { id: 'b', type: 'agent' },
        { id: 'c', type: 'output' }
      ],
      edges: [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'c' }
      ]
    };
    
    const dag = new DAGBuilder(flow);
    const sorted = dag.topologicalSort();
    
    expect(sorted).toEqual(['a', 'b', 'c']);
  });
  
  it('should detect cycles', () => {
    const flow = {
      nodes: [
        { id: 'a', type: 'agent' },
        { id: 'b', type: 'agent' }
      ],
      edges: [
        { source: 'a', target: 'b' },
        { source: 'b', target: 'a' } // Cycle!
      ]
    };
    
    expect(() => new DAGBuilder(flow)).toThrow('Cycle detected');
  });
});
```

### Integration Tests

```typescript
// Example: Workflow execution test
describe('Workflow Execution', () => {
  it('should execute simple agent workflow', async () => {
    const workflow = await createTestWorkflow({
      nodes: [
        { 
          id: 'input', 
          type: 'input',
          data: { value: 'Hello' }
        },
        {
          id: 'agent',
          type: 'agent',
          data: {
            provider: 'openai',
            model: 'gpt-3.5-turbo',
            systemPrompt: 'You are a helpful assistant'
          }
        }
      ],
      edges: [
        { source: 'input', target: 'agent' }
      ]
    });
    
    const execution = await executeWorkflow(workflow.id, {
      input: 'Say hi'
    });
    
    expect(execution.status).toBe('completed');
    expect(execution.output).toBeDefined();
  });
});
```

### E2E Tests

**Tools**: Playwright

```typescript
import { test, expect } from '@playwright/test';

test('create and execute workflow', async ({ page }) => {
  // Login
  await page.goto('/login');
  await page.fill('[name=email]', 'test@example.com');
  await page.fill('[name=password]', 'password');
  await page.click('button[type=submit]');
  
  // Create workflow
  await page.goto('/workflows');
  await page.click('text=New Workflow');
  await page.fill('[name=name]', 'Test Workflow');
  
  // Add nodes
  await page.dragAndDrop('[data-node=agent]', '.react-flow');
  
  // Configure
  await page.click('[data-node-id=agent-1]');
  await page.fill('[name=systemPrompt]', 'Test prompt');
  
  // Execute
  await page.click('text=Run');
  
  // Verify
  await expect(page.locator('.execution-status')).toHaveText('Completed');
});
```

### Performance Tests

**Tools**: Artillery, k6

```yaml
# artillery.yml
config:
  target: 'http://localhost:3001'
  phases:
    - duration: 60
      arrivalRate: 10
      name: Warm up
    - duration: 120
      arrivalRate: 50
      name: Load test

scenarios:
  - name: Execute workflow
    flow:
      - post:
          url: "/api/v1/workspaces/{{ workspaceId }}/workflows/{{ workflowId }}/execute"
          json:
            input: "Test input"
          headers:
            Authorization: "Bearer {{ token }}"
```

---

## Deployment & DevOps

### Docker Configuration

**Dockerfile.api**:
```dockerfile
FROM node:20-alpine AS base
RUN apk add --no-cache libc6-compat

FROM base AS deps
WORKDIR /app
COPY package*.json pnpm-lock.yaml ./
RUN npm install -g pnpm
RUN pnpm install --frozen-lockfile

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 apiuser

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

USER apiuser
EXPOSE 3001

CMD ["node", "dist/server.js"]
```

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_DB: agentbuilder
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "3001:3001"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/agentbuilder
      REDIS_URL: redis://redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    command: node dist/workers/execution.worker.js
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/agentbuilder
      REDIS_URL: redis://redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2

  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.web
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://api:3001

volumes:
  postgres_data:
  redis_data:
```

### CI/CD Pipeline

**GitHub Actions (.github/workflows/ci.yml)**:
```yaml
name: CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
          cache: 'pnpm'
      
      - name: Install dependencies
        run: pnpm install
      
      - name: Run linter
        run: pnpm lint
      
      - name: Run type check
        run: pnpm type-check
      
      - name: Run unit tests
        run: pnpm test:unit
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
          REDIS_URL: redis://localhost:6379
      
      - name: Run integration tests
        run: pnpm test:integration
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
      
      - name: Build
        run: pnpm build
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to production
        run: |
          # Deploy to Railway, Vercel, etc.
          # Example: vercel --prod --token=${{ secrets.VERCEL_TOKEN }}
```

### Environment Variables

**.env.example**:
```bash
# Database
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/agentbuilder"
REDIS_URL="redis://localhost:6379"

# Authentication
CLERK_SECRET_KEY="sk_test_..."
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_test_..."

# LLM Providers
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."
GOOGLE_API_KEY="..."

# Vector Database
PINECONE_API_KEY="..."
PINECONE_ENVIRONMENT="us-east-1-aws"
PINECONE_INDEX_NAME="agent-builder"

# Storage
AWS_ACCESS_KEY_ID="..."
AWS_SECRET_ACCESS_KEY="..."
AWS_REGION="us-east-1"
AWS_S3_BUCKET="agent-builder-uploads"

# Monitoring
SENTRY_DSN="https://...@sentry.io/..."
POSTHOG_API_KEY="phc_..."

# App
NODE_ENV="development"
API_URL="http://localhost:3001"
NEXT_PUBLIC_APP_URL="http://localhost:3000"
```

---

## Monitoring & Observability

### Logging

```typescript
import winston from 'winston';
import 'winston-daily-rotate-file';

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'agent-builder-api' },
  transports: [
    new winston.transports.DailyRotateFile({
      filename: 'logs/error-%DATE%.log',
      datePattern: 'YYYY-MM-DD',
      level: 'error',
      maxFiles: '30d'
    }),
    new winston.transports.DailyRotateFile({
      filename: 'logs/combined-%DATE%.log',
      datePattern: 'YYYY-MM-DD',
      maxFiles: '14d'
    })
  ]
});

if (process.env.NODE_ENV !== 'production') {
  logger.add(new winston.transports.Console({
    format: winston.format.simple()
  }));
}

export default logger;
```

### Error Tracking

```typescript
import * as Sentry from '@sentry/node';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 0.1,
  integrations: [
    new Sentry.Integrations.Http({ tracing: true }),
    new Sentry.Integrations.Express({ app })
  ]
});

// Request handler
app.use(Sentry.Handlers.requestHandler());
app.use(Sentry.Handlers.tracingHandler());

// Error handler
app.use(Sentry.Handlers.errorHandler());
```

### Metrics

```typescript
import { collectDefaultMetrics, Registry, Counter, Histogram } from 'prom-client';

const register = new Registry();

collectDefaultMetrics({ register });

const httpRequestDuration = new Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  registers: [register]
});

const executionCounter = new Counter({
  name: 'workflow_executions_total',
  help: 'Total number of workflow executions',
  labelNames: ['status', 'workflow_id'],
  registers: [register]
});

const tokenUsageCounter = new Counter({
  name: 'llm_tokens_total',
  help: 'Total LLM tokens used',
  labelNames: ['provider', 'model'],
  registers: [register]
});

// Expose metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});
```

### Health Checks

```typescript
app.get('/health', async (req, res) => {
  const health = {
    status: 'ok',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    checks: {
      database: 'unknown',
      redis: 'unknown',
      vectordb: 'unknown'
    }
  };
  
  try {
    await prisma.$queryRaw`SELECT 1`;
    health.checks.database = 'ok';
  } catch (error) {
    health.checks.database = 'error';
    health.status = 'degraded';
  }
  
  try {
    await redis.ping();
    health.checks.redis = 'ok';
  } catch (error) {
    health.checks.redis = 'error';
    health.status = 'degraded';
  }
  
  res.status(health.status === 'ok' ? 200 : 503).json(health);
});
```

---

## Success Metrics

### KPIs to Track

**User Engagement**:
- Daily/Monthly Active Users
- Workflows created per user
- Executions per workflow
- Time spent in editor

**Performance**:
- Average execution time
- P95/P99 latency
- Error rate
- Token usage per execution

**Business**:
- User retention (7-day, 30-day)
- Conversion rate (free → paid)
- Monthly Recurring Revenue
- Customer Acquisition Cost

**Technical**:
- API uptime (target: 99.9%)
- Mean Time To Recovery
- Database query performance
- Cache hit rate

---

## Appendix

### Recommended Learning Resources

1. **React Flow**: https://reactflow.dev/learn
2. **LangChain.js**: https://js.langchain.com/docs
3. **Prisma**: https://www.prisma.io/docs
4. **BullMQ**: https://docs.bullmq.io
5. **Next.js**: https://nextjs.org/docs

### Third-Party Services Needed

1. **Clerk**: Authentication ($0-$25/month)
2. **Pinecone**: Vector database ($70/month)
3. **Vercel**: Frontend hosting (Free tier available)
4. **Railway**: Backend hosting ($5-$20/month)
5. **Sentry**: Error tracking (Free tier available)

### Estimated Timeline

- **MVP (Phases 1-3)**: 6 weeks
- **Production Ready (Phases 4-5)**: 10 weeks
- **Polish & Launch (Phase 6)**: 12 weeks

### Team Composition (Recommended)

- 1-2 Full-stack developers
- 1 DevOps engineer (part-time)
- 1 UI/UX designer (part-time)
- 1 Product manager

---

## Getting Started

### Setup Instructions

```bash
# Clone repository
git clone https://github.com/your-org/ai-agent-builder.git
cd ai-agent-builder

# Install dependencies
pnpm install

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Start databases
docker-compose up -d postgres redis

# Run migrations
cd apps/api
pnpm prisma migrate dev
pnpm prisma generate

# Seed database (optional)
pnpm prisma db seed

# Start development servers
cd ../..
pnpm dev

# API: http://localhost:3001
# Web: http://localhost:3000
```

### First Steps

1. Create account at http://localhost:3000
2. Create a workspace
3. Create your first workflow
4. Add Agent + Prompt modules
5. Connect them
6. Execute!

---

## Notes for Claude Code CLI

**Priority Order**:
1. Setup project structure and databases first
2. Implement core execution engine before UI
3. Test each module independently
4. Add real-time features only after basic execution works
5. Focus on one module type at a time

**Key Decision Points**:
- Use Clerk vs NextAuth: Clerk is easier, NextAuth is more flexible
- Pinecone vs Qdrant: Pinecone is managed, Qdrant is self-hosted
- Monorepo vs separate repos: Monorepo recommended for shared types

**Critical Files to Create First**:
1. `prisma/schema.prisma`
2. `apps/api/src/services/workflow/ExecutionEngine.ts`
3. `apps/api/src/services/modules/BaseModule.ts`
4. `apps/web/src/components/flow/Canvas.tsx`

**Testing Strategy**:
- Write tests for execution engine first (most critical)
- Mock LLM responses for consistent testing
- Test each module in isolation before integration

This plan should give you everything needed to build a production-ready AI agent builder. Good luck! 🚀
