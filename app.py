"""
Chat UI for the local code index.

    chainlit run app.py          → http://localhost:8000

Same pipeline as ask.py: search → prompt → local LLM, streamed.
The settings panel (⚙ next to the input) lets you pick the repository, the number of chunks
and whether the model thinks first.
"""

import asyncio

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch

from rag.answer import LANG, answer_stream
from rag.config import EMBED_MODEL, LLM_MODEL, LLM_THINK, TOP_K
from rag.ollama import OllamaError
from rag.search import IndexMissing, list_repos, search

ALL_REPOS = "all repositories"
_END = object()


async def _iterate_in_thread(generator):
    """Consume a blocking generator (HTTP streaming) without freezing the UI."""
    while (item := await asyncio.to_thread(next, generator, _END)) is not _END:
        yield item


@cl.on_chat_start
async def start():
    repos = await asyncio.to_thread(list_repos)
    settings = await cl.ChatSettings([
        Select(id="repo", label="Repository", values=[ALL_REPOS, *repos], initial_index=0),
        Slider(id="k", label="Chunks per question (top-k)", initial=TOP_K, min=1, max=15, step=1),
        Switch(id="think", label="Let the model think first (slower)", initial=LLM_THINK),
    ]).send()
    cl.user_session.set("settings", settings)

    indexed = ", ".join(f"`{r}`" for r in repos) if repos else "_nothing yet — run `python3 index.py <repo>`_"
    await cl.Message(content=(
        "## 🔒 Local Code RAG\n"
        f"Everything runs on this machine — embeddings `{EMBED_MODEL}`, answers `{LLM_MODEL}` via Ollama.\n\n"
        f"**Indexed:** {indexed}\n\n"
        "**Try:**\n"
        "- *Which step definition checks that the searchbar is visible?*\n"
        "- *How is the WebDriver created for Firefox?*\n"
        "- *What happens after a scenario fails?*\n"
        "- *Which scenarios use more than one user?*"
    )).send()


@cl.on_settings_update
async def update_settings(settings):
    cl.user_session.set("settings", settings)


@cl.on_message
async def main(message: cl.Message):
    settings = cl.user_session.get("settings") or {}
    repo = settings.get("repo")
    repo = None if repo in (None, ALL_REPOS) else repo
    k = int(settings.get("k", TOP_K))
    think = bool(settings.get("think", LLM_THINK))

    # 1. Retrieval
    async with cl.Step(name="Search the code index", type="retrieval") as step:
        step.input = message.content
        try:
            hits = await asyncio.to_thread(search, message.content, k, repo)
        except (IndexMissing, OllamaError) as e:
            await cl.Message(content=f"❌ {e}").send()
            return
        step.output = "\n".join(f"- `{h.repo}/{h.location}` · {h.symbol} · score {h.score:.3f}" for h in hits)

    # Code of each hit, shown in the side panel when its name is clicked.
    # Chainlit links an element by its exact name in the message text — names must be unique.
    names = []
    for h in hits:
        name = h.short_location
        if name in names:
            name = f"{h.repo}/{name}"
        names.append(name)
    elements = [
        cl.Text(name=n, content=h.text, display="side", language=LANG.get(h.language, ""))
        for n, h in zip(names, hits)
    ]

    # 2. Generation, streamed
    answer = cl.Message(content="", elements=elements)
    thinking_step = None
    stats = {}
    try:
        async for kind, value in _iterate_in_thread(answer_stream(message.content, hits, think=think)):
            if kind == "thinking":
                if thinking_step is None:
                    thinking_step = cl.Step(name="Thinking", type="llm")
                    await thinking_step.__aenter__()
                await thinking_step.stream_token(value)
            elif kind == "content":
                if thinking_step is not None:
                    await thinking_step.__aexit__(None, None, None)
                    thinking_step = None
                await answer.stream_token(value)
            elif kind == "done":
                stats = value
    except OllamaError as e:
        await answer.stream_token(f"\n\n❌ {e}")
    finally:
        if thinking_step is not None:
            await thinking_step.__aexit__(None, None, None)

    sources = "\n".join(
        f"[{i}] {n} — `{h.repo}/{h.path}` · {h.symbol}" for i, (n, h) in enumerate(zip(names, hits), 1)
    )
    footer = (f"\n\n_⏱ {stats['seconds']:.1f}s · prompt {stats['prompt_tokens']} tokens · "
              f"{stats['tokens_per_second']:.1f} tok/s_" if stats else "")
    await answer.stream_token(f"\n\n---\n**Sources** (click to view the code)\n{sources}{footer}")
    await answer.send()
