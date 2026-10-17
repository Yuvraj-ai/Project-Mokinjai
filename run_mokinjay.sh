#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PIDS=()

cleanup() {
  echo ""
  echo "Shutting down services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  echo "All services stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "========================================="
echo "  Mokinjay - AI Agent Builder"
echo "========================================="
echo ""

# --- Check prerequisites ---
echo "[1/6] Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Please install Python 3.12+."
  exit 1
fi

if ! command -v node &>/dev/null; then
  echo "ERROR: node not found. Please install Node.js 20+."
  exit 1
fi

# --- Start PostgreSQL ---
echo "[2/6] Checking PostgreSQL..."
if pg_isready -q 2>/dev/null; then
  echo "  PostgreSQL is running."
else
  echo "  Starting PostgreSQL..."
  sudo systemctl start postgresql
  sleep 2
  if ! pg_isready -q 2>/dev/null; then
    echo "ERROR: Failed to start PostgreSQL."
    exit 1
  fi
  echo "  PostgreSQL started."
fi

# No database is provisioned here. The application connects using DATABASE_URL
# from the repo-root .env — a hosted instance in the current setup — so creating a
# local database would only produce one the app never touches. The local
# PostgreSQL started above exists for the test suite, which runs against
# `mokinjay_test` and refuses any database whose name does not end in `_test`.

# --- Start Redis ---
echo "[3/6] Checking Redis..."
if redis-cli ping &>/dev/null; then
  echo "  Redis is running."
else
  # Try systemctl first
  if sudo systemctl start redis 2>/dev/null; then
    sleep 1
    echo "  Redis started via systemd."
  elif command -v docker &>/dev/null; then
    echo "  Starting Redis via Docker..."
    if docker ps -a --format '{{.Names}}' | grep -q redis-agentbuilder; then
      docker start redis-agentbuilder &>/dev/null
    else
      docker run -d --name redis-agentbuilder -p 6379:6379 redis:7-alpine &>/dev/null
    fi
    sleep 2
    echo "  Redis started via Docker."
  else
    echo "ERROR: Cannot start Redis. Install redis or docker."
    exit 1
  fi
fi

# --- Setup backend venv if needed ---
echo "[4/6] Setting up backend..."
if [ ! -d "$BACKEND_DIR/venv" ]; then
  echo "  Creating virtual environment..."
  python3 -m venv "$BACKEND_DIR/venv"
  echo "  Installing Python dependencies..."
  "$BACKEND_DIR/venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
else
  echo "  Virtual environment exists."
fi

# Copy .env if it doesn't exist
if [ ! -f "$PROJECT_DIR/.env" ] && [ -f "$PROJECT_DIR/.env.example" ]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  echo "  Created .env from .env.example (edit it to add your API keys)."
fi

# Migrations are deliberately NOT run here. The application connects using
# DATABASE_URL from the repo-root .env, which points at a hosted instance, and
# Alembic refuses a remote target unless ALLOW_REMOTE_MIGRATIONS=1 is set. That
# opt-in exists so DDL against a remote database stays a deliberate act rather
# than a side effect of starting the app. Run migrations yourself when the schema
# changes:
#
#   cd backend && ./venv/bin/python -m alembic upgrade head
#   (prefix ALLOW_REMOTE_MIGRATIONS=1 when the target is the hosted instance)
cd "$BACKEND_DIR"

# --- Setup frontend if needed ---
echo "[5/6] Setting up frontend..."
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "  Installing npm dependencies..."
  cd "$FRONTEND_DIR"
  npm install --silent
else
  echo "  Node modules exist."
fi

# --- Start all services ---
echo "[6/6] Starting services..."
echo ""

# Backend
cd "$BACKEND_DIR"
"$BACKEND_DIR/venv/bin/uvicorn" app.main:app --reload --port 8001 &
PIDS+=($!)
echo "  Backend    -> http://localhost:8001"

# Celery worker
"$BACKEND_DIR/venv/bin/celery" -A app.workers.celery_app worker --loglevel=warning &
PIDS+=($!)
echo "  Celery     -> connected to Redis"

# Frontend
cd "$FRONTEND_DIR"
npx vite --port 5173 &
PIDS+=($!)
echo "  Frontend   -> http://localhost:5173"

echo ""
echo "========================================="
echo "  All services running!"
echo "  Open http://localhost:5173 in browser"
echo "  Press Ctrl+C to stop all services"
echo "========================================="
echo ""

wait
