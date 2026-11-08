# Local Code RAG Workshop

Ask questions about your own codebase with an AI agent — **with everything running on your machine**.

In this workshop you build a small Retrieval-Augmented Generation (RAG) pipeline over a test-automation
codebase in Kotlin or Java (Selenium / Cucumber), expose it as an MCP tool, and use it from the [goose](https://github.com/aaif-goose/goose)
agent — powered by a local LLM via [Ollama](https://ollama.com).

```
 Your repo ──► chunk ──► embed (Ollama) ──► ChromaDB ──► MCP server ──► goose (local LLM via Ollama)
```

> [!IMPORTANT]
> **"Local" is only true end-to-end if goose itself uses a local model.**
> The RAG tool hands code snippets to the agent. If goose is configured with a cloud provider
> (Anthropic, OpenAI, …), those snippets leave your machine. Step 1 sets goose up with Ollama and shows
> how to verify it.

## Workshop steps

| # | Step | Status |
|---|------|--------|
| 0 | [Preparation](docs/preparation.md) — before the workshop, at home | ✅ |
| 1 | [Set up goose with a local LLM](docs/01-setup-goose-ollama.md) | ✅ |
| 2 | [Index a codebase](docs/02-index-a-codebase.md) — chunking, embeddings, ChromaDB | ✅ |
| 3 | [Ask questions](docs/03-query.md) — search and answers in the terminal | ✅ |
| 4 | [Connect it to goose](docs/04-connect-goose.md) — MCP extension, desktop & CLI | ✅ |
| 5 | [Test your RAG](docs/05-test-your-rag.md) — can I trust the answer? Plus take-home eval scripts | ✅ |
| 6 | [Exercises](docs/06-exercises.md) — let goose write a test; take-home: chunking & embedding experiments | ✅ |

## Before the workshop

> [!IMPORTANT]
> **Please prepare at home** — the models are several GB.
> Everything you need is in **[Preparation](docs/preparation.md)** (about an hour, mostly downloads).

## Repository layout

```
docs/            step-by-step guides
rag/             the RAG building blocks
  chunking.py    how code is cut into pieces
  ollama.py      embeddings via the local Ollama server
  store.py       ChromaDB (local vector database)
  search.py      retrieval
  answer.py      prompt + answer generation
  golden.py      golden question sets
  config.py      settings, overridable via environment variables
index.py         build / update the index
search.py        retrieval only — which chunks match a question?
ask.py           question → answer with sources, in the terminal
mcp_server.py    MCP server — goose starts it as an extension
eval_retrieval.py  retrieval eval: recall@k and MRR against a golden set
eval_answers.py    answer eval: pass rate over several runs
eval/            golden question sets
scripts/         setup check, goose extension settings, MCP test without goose
exercises/       reference solutions for the exercises
```

## License

[MIT](LICENSE) © Boris Wrubel
