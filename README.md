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
| 1 | [Set up goose with a local LLM](docs/01-setup-goose-ollama.md) | ✅ |
| 2 | [Index a codebase](docs/02-index-a-codebase.md) — chunking, embeddings, ChromaDB | ✅ |
| 3 | [Ask questions](docs/03-query.md) — terminal & chat UI | ✅ |
| 4 | [Connect it to goose](docs/04-connect-goose.md) — MCP extension, desktop & CLI | ✅ |
| 5 | Test your RAG: golden questions & recall@k | 🚧 |
| 6 | Exercises | 🚧 |

## Before the workshop

The models are several GB — **download them at home, not over conference Wi-Fi.**

1. Work through [Step 1](docs/01-setup-goose-ollama.md) — goose, Ollama, `qwen3:8b`.
2. Prepare the environment from [Step 2](docs/02-index-a-codebase.md):
   ```bash
   git clone https://github.com/swtst-at/local-code-rag-workshop.git
   git clone https://github.com/secugrow/generated_kotlin.git   # or generated_java — pick one
   cd local-code-rag-workshop
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ollama pull nomic-embed-text
   ```
3. Run the setup check — everything should be green:
   ```bash
   python3 scripts/check_setup.py
   ```

### Hardware

| Machine | Expectation |
|---------|-------------|
| GPU / Apple Silicon / iGPU with ≥ 16 GB shared RAM | Comfortable |
| CPU only, 16 GB RAM | Works, but slow — use the smaller fallback model from Step 1 |
| < 16 GB RAM | Not recommended |

Linux (Ubuntu) is the reference platform; macOS works with the notes in Step 1.

## Repository layout

```
docs/            step-by-step guides
rag/             the RAG building blocks
  chunking.py    how code is cut into pieces
  ollama.py      embeddings via the local Ollama server
  store.py       ChromaDB (local vector database)
  search.py      retrieval
  answer.py      prompt + answer generation
  config.py      settings, overridable via environment variables
index.py         build / update the index
search.py        retrieval only — which chunks match a question?
ask.py           question → answer with sources, in the terminal
app.py           chat UI (chainlit run app.py)
mcp_server.py    MCP server — goose starts it as an extension
scripts/         setup check, goose extension settings
```

## License

[MIT](LICENSE) © Boris Wrubel
