#!/usr/bin/env python3
"""
MCP server — makes the local code index available to goose (or any other MCP client).

goose starts this script itself and talks to it over stdin/stdout (the "stdio" transport).
You never run it by hand, except to test it:

    npx @modelcontextprotocol/inspector .venv/bin/python mcp_server.py

Tools:
    search_code        semantic search over the index → code chunks with file and line numbers
    list_repositories  which repositories are indexed
    read_lines         read more lines around a hit, straight from the file

Note: there is no "answer" tool. goose's own model reads the chunks and answers —
one model, one context, no second LLM call. That also means goose's system prompt is used,
not ours — the answering rules travel inside the tool results (see RESULT_NOTE below).

Environment: MCP_ANSWER_RULES=off removes the rules — for a before/after comparison.

IMPORTANT for stdio servers: never print() to stdout — stdout carries the protocol.
Log to stderr instead.
"""

import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

import os

from rag.config import EMBED_MODEL, TOP_K
from rag.ollama import OllamaError
from rag.search import IndexMissing, list_repos, search

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="[local-code-rag] %(message)s")
log = logging.getLogger(__name__)

MAX_READ_LINES = 200

# ── Where does the prompt live? ───────────────────────────────────────────────
# In ask.py we own the system prompt. In goose we do not — goose writes the answer with its own
# system prompt. The only text we control is what this server returns. So the answering rules go
# into (1) the server instructions and (2) a short note at the end of every search result,
# which a small model reads right before it answers.
#
# For a before/after comparison:  MCP_ANSWER_RULES=off  (set it in the extension's environment)
ANSWER_RULES = os.environ.get("MCP_ANSWER_RULES", "on").lower() != "off"

INSTRUCTIONS = (
    "Local semantic index of test-automation code (Kotlin, Java, Cucumber feature files). "
    "For any question about this code, call search_code first. Answer only from the returned code "
    "and cite file paths with line numbers. Use read_lines when a chunk is cut off. "
    "Never invent classes, methods, files or steps that you have not seen in a tool result."
)

RESULT_NOTE = """---
Note for answering:
- These are the top {k} semantic matches for this query, not the whole codebase.
- If they do not answer the question, call search_code once more with different words
  (synonyms, class or method names you would expect).
- If that does not help either, say that it was not found in the searched code. Stop there.
- Do not guess file, class or step names. Do not describe code you have not seen.
- Talk about "the code", not about "chunks" or "snippets"."""

mcp = FastMCP("local-code-rag", instructions=INSTRUCTIONS if ANSWER_RULES else None)


@mcp.tool()
def search_code(query: str, k: int = TOP_K, repo: str | None = None) -> str:
    """Semantic search over the locally indexed codebase (Selenium/Appium test automation in
    Kotlin or Java, Cucumber step definitions and .feature files).

    Use this FIRST for every question about the code. Describe what you are looking for in
    natural language, e.g. "where is the Firefox WebDriver created".

    Args:
        query: what to look for, in natural language
        k: number of chunks to return (default 5, max 15)
        repo: optional repository name to restrict the search (see list_repositories)
    """
    k = max(1, min(int(k), 15))
    log.info("search_code %r k=%s repo=%s", query, k, repo)
    try:
        hits = search(query, k=k, repo=repo or None)
    except (IndexMissing, OllamaError) as e:
        return f"ERROR: {e}"
    if not hits:
        return "No matching code found." + (f"\n{RESULT_NOTE.format(k=k)}" if ANSWER_RULES else "")

    parts = [f"Search results for: {query}\n"]
    for i, h in enumerate(hits, 1):
        parts.append(
            f"[{i}] {h.repo}/{h.location}  ({h.symbol or 'code'}, score {h.score:.2f})\n"
            f"```{h.language}\n{h.text}\n```"
        )
    if ANSWER_RULES:
        parts.append(RESULT_NOTE.format(k=len(hits)))
    return "\n\n".join(parts)


@mcp.tool()
def list_repositories() -> str:
    """List the repositories in the local code index."""
    repos = list_repos()
    if not repos:
        return "The index is empty. Run: python3 index.py <path-to-repo>"
    return "Indexed repositories: " + ", ".join(repos)


@mcp.tool()
def read_lines(repo: str, path: str, start_line: int, end_line: int) -> str:
    """Read lines of an indexed file, e.g. to see more context around a search_code hit.

    Args:
        repo: repository name as shown by search_code (e.g. "generated_kotlin")
        path: file path inside the repository as shown by search_code
        start_line: first line (1-based)
        end_line: last line (inclusive, at most 200 lines per call)
    """
    log.info("read_lines %s/%s:%s-%s", repo, path, start_line, end_line)
    root = _repo_root(repo)
    if root is None:
        return f"ERROR: unknown repository '{repo}'. Known: {', '.join(list_repos()) or 'none'}"

    file = (root / path).resolve()
    if not file.is_relative_to(root):           # no "../../etc/passwd"
        return "ERROR: path is outside the repository"
    if not file.is_file():
        return f"ERROR: file not found: {path}"

    lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(1, int(start_line))
    end = min(len(lines), int(end_line), start + MAX_READ_LINES - 1)
    if start > len(lines):
        return f"ERROR: {path} has only {len(lines)} lines"
    numbered = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(start, end + 1))
    return f"{repo}/{path}:{start}-{end} (of {len(lines)} lines)\n```\n{numbered}\n```"


def _repo_root(repo: str) -> Path | None:
    """Look up the repository folder that was recorded at indexing time."""
    from rag.store import get_collection
    try:
        metas = get_collection(create=False).get(where={"repo": repo}, limit=1, include=["metadatas"])["metadatas"]
    except Exception:
        return None
    if not metas or not metas[0].get("repo_path"):
        return None
    return Path(metas[0]["repo_path"]).resolve()


if __name__ == "__main__":
    log.info("starting — embeddings %s, index %s", EMBED_MODEL, ", ".join(list_repos()) or "empty")
    mcp.run()   # stdio transport
