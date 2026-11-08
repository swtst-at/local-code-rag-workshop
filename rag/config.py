"""
Configuration — everything can be overridden with environment variables.

    EMBED_MODEL=qwen3-embedding:0.6b python3 index.py ../generated_kotlin
"""

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
# The model that writes answers. Same as goose uses → only one large model to download.
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")
# qwen3 "thinks" before answering. Off by default for RAG answers: about 3× faster, similar quality.
LLM_THINK = os.environ.get("LLM_THINK", "false").lower() in ("1", "true", "yes")
TOP_K = int(os.environ.get("TOP_K", 5))     # how many chunks are retrieved per question
# System prompt for answers: "strict" (default) or "basic" (first version, for comparison) — see rag/answer.py
PROMPT = os.environ.get("PROMPT", "strict")
DB_PATH = Path(os.environ.get("RAG_DB_PATH", PROJECT_ROOT / "db"))

# ── Which files are indexed ───────────────────────────────────────────────────
# file extension → language. The language decides which chunker is used (rag/chunking.py).
# Structure-aware chunkers exist for kotlin, java and gherkin; every other language
# falls back to the "generic" chunker (cut at blank lines).
FILE_TYPES = {
    ".kt": "kotlin",
    ".java": "java",
    ".feature": "gherkin",
}

# Add more without touching the code:  EXTRA_FILE_TYPES=".py,.ts,.xml"  → generic chunker
for ext in filter(None, os.environ.get("EXTRA_FILE_TYPES", "").split(",")):
    ext = ext.strip() if ext.strip().startswith(".") else f".{ext.strip()}"
    FILE_TYPES.setdefault(ext, "generic")

IGNORE_DIRS = {".git", ".gradle", ".idea", "build", "target", "out", "generated", "node_modules",
               "__pycache__", ".venv", "venv"}

# ── Chunking ──────────────────────────────────────────────────────────────────
MAX_CHUNK_CHARS = int(os.environ.get("MAX_CHUNK_CHARS", 1200))   # ~4 characters per token for code
OVERLAP_LINES = 3           # only used when a single declaration is too large and must be cut
# CHUNKER=generic ignores the language and cuts every file at blank lines — for comparison.
FORCE_GENERIC = os.environ.get("CHUNKER", "").lower() == "generic"

EMBED_BATCH_SIZE = 32       # chunks per request to Ollama


def collection_name(embed_model: str = EMBED_MODEL) -> str:
    """One collection per embedding model (and chunker variant).

    Different models produce vectors of different sizes and meaning —
    they must never be mixed in one collection. This also lets you compare
    models and chunkers side by side.
    """
    name = "code__" + re.sub(r"[^a-zA-Z0-9_-]", "_", embed_model)
    return name + "__generic" if FORCE_GENERIC else name
