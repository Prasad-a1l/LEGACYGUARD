from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Prevent LangSmith/LangChain telemetry from stalling the harness.
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_CALLBACKS_BACKGROUND", "false")

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = ROOT_DIR / "data"
REPO_PATH = Path(os.getenv("REPO_PATH", ROOT_DIR / "nexapay-core")).resolve()

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'legacyguard.db'}")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_ENABLED = os.getenv("QDRANT_ENABLED", "0") in {"1", "true", "True", "yes"}
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

INTERNAL_MATCH_THRESHOLD = 0.70
HIGH_CONFIDENCE = 0.80
ESCALATE_BELOW = 0.55
