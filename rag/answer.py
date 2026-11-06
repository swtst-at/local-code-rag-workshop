"""
Generation — let the local LLM answer, based only on the retrieved chunks.

This is the "G" in RAG. The prompt tells the model to stay inside the retrieved code and to cite it,
so you can check every claim against the code.

Two system prompts are kept side by side so you can compare them:

    python3 ask.py "What does the login step do?" --prompt basic
    python3 ask.py "What does the login step do?"                   # strict (default)
"""

from .config import LLM_MODEL, LLM_THINK, PROMPT
from .ollama import chat_stream
from .search import Hit

PROMPTS = {
    # First version. Looks reasonable — but watch what happens when the answer is not in the code:
    # - "excerpts" leaks into the answer (our internal word, meaningless to the user)
    # - "suggest what to search for" invites the model to invent file names
    "basic": """\
You are a senior test-automation engineer answering questions about a codebase.

Rules:
- Answer ONLY from the code excerpts provided. Do not invent classes, methods or behaviour.
- Cite the excerpts you use with their number, e.g. [2].
- If the excerpts do not contain the answer, say so plainly and suggest what to search for instead.
- Be concise. Use short code snippets only when they help.
""",
    # Improved version: user-facing wording, no speculation, honest about the limits of retrieval.
    "strict": """\
You are a senior test-automation engineer answering questions about a codebase.
A search has returned the pieces of code below. They are the best matches — not the whole codebase.

Rules:
- Use ONLY the code below. Never invent classes, methods, files, steps or behaviour.
- Cite what you use by its number and file name, e.g. [2] Hooks.kt.
- Talk about "the code" or "the searched code". Never use words like "excerpts", "chunks" or "context".
- If the code below does not answer the question, reply that you could not find it in the searched
  code, and stop. Do not guess file names, do not describe code you have not seen.
- Never claim that something does not exist in the codebase — you only see the search results.
- Be concise. Quote short pieces of code only when they help.
""",
}

LANG = {"kotlin": "kotlin", "java": "java", "gherkin": "gherkin"}


def build_context(hits: list[Hit]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(
            f"[{i}] {h.repo}/{h.location}  ({h.symbol or 'code'})\n"
            f"```{LANG.get(h.language, '')}\n{h.text}\n```"
        )
    return "\n\n".join(parts)


def build_messages(question: str, hits: list[Hit], prompt: str = PROMPT) -> list[dict]:
    if prompt not in PROMPTS:
        raise ValueError(f"Unknown prompt '{prompt}' — choose one of: {', '.join(PROMPTS)}")
    label = "Code excerpts" if prompt == "basic" else "Code found by the search"
    return [
        {"role": "system", "content": PROMPTS[prompt]},
        {"role": "user", "content": f"{label}:\n\n{build_context(hits)}\n\n---\n\nQuestion: {question}"},
    ]


def answer_stream(question: str, hits: list[Hit], model: str = LLM_MODEL, think: bool = LLM_THINK,
                  prompt: str = PROMPT):
    """Yields ("thinking" | "content", text) while streaming, then ("done", stats)."""
    yield from chat_stream(build_messages(question, hits, prompt), model=model, think=think)
