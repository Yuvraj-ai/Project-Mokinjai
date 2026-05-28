#!/usr/bin/env python3
"""Safe development server for the Mokinjay backend.

Runs uvicorn with auto-reload, validates required env vars,
and checks that dependencies are installed before starting.
"""

import os
import sys
import importlib.util
from pathlib import Path

# Resolve backend root and ensure .env is loaded
BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

# Try loading .env via dotenv if available
def load_env():
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        print("[WARN] .env file not found — using config defaults.")
        return
    spec = importlib.util.find_spec("dotenv")
    if spec:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    else:
        # Manual fallback: parse key=value lines
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def check_dependencies():
    """Verify critical packages are importable."""
    missing = []
    for pkg in ("fastapi", "uvicorn", "sqlalchemy", "pydantic_settings"):
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)
    if missing:
        print("[ERROR] Missing dependencies. Install them with:")
        print(f"  pip install -r {BACKEND_DIR / 'requirements.txt'}")
        print(f"  (missing: {', '.join(missing)})")
        sys.exit(1)


def validate_env():
    """Warn about empty required env vars."""
    warnings = []
    secret = os.getenv("JWT_SECRET_KEY", "")
    if secret == "your-super-secret-key-change-in-production":
        warnings.append("JWT_SECRET_KEY is still the default placeholder")
    if not os.getenv("OPENAI_API_KEY"):
        warnings.append("OPENAI_API_KEY is empty")
    for w in warnings:
        print(f"[WARN] {w}")


def main():
    load_env()
    check_dependencies()
    validate_env()

    from app.logging import logger

    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))

    logger.info(f"Starting Mokinjay backend on {host}:{port}")
    logger.info(f"Docs available at http://localhost:{port}/docs")
    logger.info("Press Ctrl+C to stop")

    import uvicorn

    logger.info("Uvicorn server initialized")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
