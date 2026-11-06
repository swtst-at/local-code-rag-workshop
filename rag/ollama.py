"""
Minimal Ollama client — only the Python standard library.

All requests go to OLLAMA_URL (default http://localhost:11434). Nothing else is contacted.
"""

import json
import urllib.error
import urllib.request

from .config import EMBED_BATCH_SIZE, EMBED_MODEL, OLLAMA_URL


class OllamaError(RuntimeError):
    pass


def _post(path: str, payload: dict, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")
        raise OllamaError(f"Ollama {path} → HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise OllamaError(f"Ollama not reachable at {OLLAMA_URL} ({e.reason}). Is it running?") from e


def _get(path: str, timeout: int = 5) -> dict:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}{path}", timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        raise OllamaError(f"Ollama not reachable at {OLLAMA_URL} ({e.reason}). Is it running?") from e


def require_model(model: str) -> None:
    """Fail early with a helpful message if a model has not been pulled."""
    names = {m.get("name", "") for m in _get("/api/tags").get("models", [])}
    wanted = model if ":" in model else f"{model}:latest"
    if wanted not in names:
        raise OllamaError(f"Model '{model}' is not installed. Run:  ollama pull {model}")


# ── Embeddings ────────────────────────────────────────────────────────────────
#
# Many embedding models were trained with task prefixes. Leaving them out
# measurably hurts retrieval quality. The model card tells you which ones to use.

PREFIXES = {
    # family: (document prefix, query prefix)
    "nomic-embed-text": ("search_document: ", "search_query: "),
    "embeddinggemma": ("title: none | text: ", "task: code retrieval | query: "),
    "qwen3-embedding": (
        "",
        "Instruct: Given a question about a codebase, retrieve the relevant code\nQuery: ",
    ),
}


def _prefixes(model: str) -> tuple[str, str]:
    family = model.split(":")[0].split("/")[-1]
    return PREFIXES.get(family, ("", ""))


def embed_documents(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    """Embed chunks for the index — batched: one request per EMBED_BATCH_SIZE chunks."""
    doc_prefix, _ = _prefixes(model)
    vectors = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = [doc_prefix + t for t in texts[i : i + EMBED_BATCH_SIZE]]
        vectors.extend(_post("/api/embed", {"model": model, "input": batch})["embeddings"])
    return vectors


def embed_query(text: str, model: str = EMBED_MODEL) -> list[float]:
    """Embed a search question — with the *query* prefix."""
    _, query_prefix = _prefixes(model)
    return _post("/api/embed", {"model": model, "input": [query_prefix + text]})["embeddings"][0]


# ── Chat (answer generation) ──────────────────────────────────────────────────

def chat_stream(messages: list[dict], model: str, think: bool = False, timeout: int = 600):
    """Stream a chat answer from Ollama.

    Yields ("thinking", text), ("content", text) and finally ("done", stats).
    `think=False` switches off the reasoning phase of models like qwen3 — much faster for RAG answers.
    """
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps({"model": model, "messages": messages, "stream": True, "think": think}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for line in r:
                if not line.strip():
                    continue
                part = json.loads(line)
                if "error" in part:
                    raise OllamaError(part["error"])
                msg = part.get("message", {})
                if msg.get("thinking"):
                    yield "thinking", msg["thinking"]
                if msg.get("content"):
                    yield "content", msg["content"]
                if part.get("done"):
                    yield "done", {
                        "prompt_tokens": part.get("prompt_eval_count", 0),
                        "answer_tokens": part.get("eval_count", 0),
                        "seconds": part.get("total_duration", 0) / 1e9,
                        "tokens_per_second": part.get("eval_count", 0)
                        / max(part.get("eval_duration", 1) / 1e9, 1e-9),
                    }
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")
        raise OllamaError(f"Ollama /api/chat → HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise OllamaError(f"Ollama not reachable at {OLLAMA_URL} ({e.reason}). Is it running?") from e
