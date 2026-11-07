# Step 4 — Connect the index to goose

Goal: ask goose about the code in plain language — goose decides by itself when to search the index.

```
 you ──► goose ──► qwen3:8b decides: "I need code" ──► search_code (MCP) ──► ChromaDB
                        ▲                                                       │
                        └───────────── code chunks with file:line ◄─────────────┘
```

In Step 3 *our* script searched and then asked the LLM. Now the **agent** is in charge:
it reads your question, calls the search tool when it needs code, may search again or read more lines,
and then answers.

---

## 4.1 MCP in one minute

The **Model Context Protocol (MCP)** is a standard way to give an AI agent tools.
An MCP server announces its tools (name, description, parameters); the agent's LLM reads those
descriptions and decides when to call them.

Our server, `mcp_server.py`, offers three tools:

| Tool | What it does |
|------|--------------|
| `search_code(query, k, repo)` | semantic search over the index — same as `search.py` |
| `list_repositories()` | which repositories are indexed |
| `read_lines(repo, path, start_line, end_line)` | read more lines around a hit, straight from the file |

There is deliberately **no** "answer" tool: goose's own model reads the chunks and answers.
One model, one context — no second LLM call.

It uses the **stdio** transport: goose starts the server as a child process and talks to it over
stdin/stdout. No port, no server to keep running.

---

## 4.2 Get the exact settings

The extension needs absolute paths — goose does not know about your activated venv.
Let the helper print them for your checkout:

```bash
python3 scripts/goose_extension.py
```

```
goose Desktop  →  Extensions  →  Add custom extension
───────────────────────────────────────────────────────
  Extension Name   local-code-rag
  Type             STDIO
  Description      Local semantic search over the indexed code
  Command          /home/you/…/local-code-rag-workshop/.venv/bin/python /home/you/…/local-code-rag-workshop/mcp_server.py
  Timeout          300
…
```

The **Command** is one line made of two absolute paths separated by a space:

| Part | Example | Meaning |
|------|---------|---------|
| program | `/home/you/repos/local-code-rag-workshop/.venv/bin/python` | the Python **of your venv** — it has `chromadb` and `mcp` installed; the system Python does not |
| script | `/home/you/repos/local-code-rag-workshop/mcp_server.py` | the file Python runs |

### Test the command in a terminal first

Paste the exact command into a terminal:

```bash
/home/you/repos/local-code-rag-workshop/.venv/bin/python /home/you/repos/local-code-rag-workshop/mcp_server.py
```

✅ Correct: `[local-code-rag] starting — embeddings nomic-embed-text, index generated_kotlin` — then
**nothing happens**. The server is waiting for goose on stdin. Stop it with `Ctrl+C`.

❌ `No such file or directory` → a path is wrong. ❌ `ModuleNotFoundError` → not the venv's Python.

---

## 4.3 goose Desktop

> UI in German or another language? **Settings → App → Language → English** — then the labels
> match this guide.

1. Open **Extensions** in the sidebar → **Add custom extension**
2. Fill in the values from 4.2 — **Type: STDIO**, **Command:** the line you just tested
3. Save — the extension should show up as enabled

### Use only the RAG extension

By default the **Developer** extension is on as well. It can run shell commands and read files —
so goose could simply `grep` the repository and **bypass the RAG**. For the workshop, switch it off:

On the **Extensions** page, turn **off everything except `local-code-rag`**.

| Why | |
|-----|---|
| Clear demo | every answer provably comes from the index |
| Faster | each extension adds its tool descriptions to *every* request. Developer alone is several thousand tokens — on a laptop that is many seconds of prompt processing |
| More reliable | an 8B model picks the right tool more reliably from 3 tools than from 15 |

CLI: `goose configure` → **Toggle Extensions**. CLI and desktop share the configuration.

Start a **new chat** (extensions are loaded when a session starts) and ask:

```
Which step definition checks that the searchbar is visible?
```

You should see a tool call `search_code` in the chat — expand it to see the search query goose
wrote itself — followed by an answer with file paths and line numbers.

**Discussion:** switch Developer back on and ask again. Does goose use `search_code` or `grep`?
For a small repository and exact names, `grep` often wins. RAG shines in large codebases and for
questions whose words do not appear in the code ("how is the browser started?" vs. `createWebDriver`).

## 4.4 goose CLI

Either for one session:

```bash
goose session --with-extension "/home/you/…/.venv/bin/python /home/you/…/mcp_server.py"
```

or permanently with the `config.yaml` block printed in 4.2. CLI and desktop share
`~/.config/goose/config.yaml`, so an extension added in the desktop app is available in the CLI too.

---

## 4.5 Working with a local model

`qwen3:8b` is good at tool calling, but smaller than cloud models. A few habits help:

| Tip | Why |
|-----|-----|
| Mention the index: *"Search the code index …"* | the model reliably picks `search_code` |
| One question at a time | long multi-part prompts make small models skip tool calls |
| Expect ~1 minute for the first answer | goose's system prompt and tool definitions are read first |
| Start a new session after re-indexing | not required — the server reads the current index on every call |

Make it permanent for a project with a `.goosehints` file in the folder you start goose from:

```
For questions about the test-automation code, always use the local-code-rag search_code tool first.
Cite file paths with line numbers.
```

### Good prompts to try

```
Search the code index: how is the WebDriver created for Firefox?
Which scenarios in the feature files use more than one user?
Find the hook that runs after each scenario and explain what it does. Read more lines if needed.
Is there a login step in the code? Search before you answer.
```

Watch the tool calls: does goose search more than once? Does it use `read_lines` when a chunk is cut?

---

## 4.6 Where does the prompt live?

Ask goose the trap question from Step 3:

```
What does the login step do?
```

An answer we got from goose **without** answer rules in the server:

> The provided code snippets do not explicitly mention a "login step." … it might be defined in another
> step definition file (e.g., `LoginSteps.kt`) …

The same two problems as with the `basic` prompt in Step 3.5 — jargon and an invented file name —
although `ask.py` already uses the improved `strict` prompt. Why?

| | `ask.py` / chat UI | goose |
|---|---|---|
| Who writes the system prompt? | **we** (`rag/answer.py`) | **goose** |
| What do we control? | everything | only the text our MCP server returns |

**In an agent setup, you do not own the prompt.** The rules have to travel with the tool.
`mcp_server.py` therefore puts them in two places:

| Place | Effect |
|-------|--------|
| Server **instructions** (sent once when goose connects) | general rules — answer only from tool results, never invent names |
| A **note at the end of every `search_code` result** | read by the model right before it answers — the most effective place for small models |

The note also tells the agent to **search again with different words** before giving up —
something a fixed pipeline like `ask.py` cannot do, but an agent can.

### Compare before / after

Set the environment variable `MCP_ANSWER_RULES=off` for the extension (desktop: environment
variables in the extension settings; config file: `envs: {MCP_ANSWER_RULES: "off"}`), start a new chat,
ask the login question. Then remove it again and compare. Run each a few times — a single answer
proves little (see Step 5).

---

## 4.7 Is it still local?

| Component | Runs on |
|-----------|---------|
| `mcp_server.py`, ChromaDB, embeddings (`nomic-embed-text`) | your machine |
| goose's model | **whatever provider goose is configured with** |

The code chunks returned by `search_code` go into goose's context — and from there to goose's
model. With the Ollama provider from Step 1, everything stays local. With a cloud provider,
**the chunks leave your machine**. `python3 scripts/check_setup.py` shows the active provider.

---

## 4.8 When the local model is not enough

An 8B model on a laptop has limits: a context of about 32k tokens, a few tokens per second, and
weaker planning over many files. Signs that you hit them:

- the context indicator approaches `…/33k`, or goose starts to forget rules and tools
- goose loops, stops calling tools, or gives up on a task that spans several files
- a single answer takes minutes

Then you can switch **this task** to a cloud model, e.g. Claude.

> [!WARNING]
> With a cloud model, **everything goose sees goes to that provider**: your prompts, the
> `search_code` results, and every file the Developer extension reads.
> The workshop’s demo projects are public — fine. For company code, check your policy first.

| | Local (`qwen3:8b` via Ollama) | Cloud (e.g. Claude) |
|---|---|---|
| Code leaves the machine | no | **yes** |
| Cost | none | per token, needs an API key |
| Context | ~32k tokens | much larger, e.g. 200k |
| Multi-file tasks, planning | limited | much stronger |
| Speed on a laptop | slow first answer, ~14 tokens/s | depends on the network, usually faster |

### goose desktop

1. Once: **Settings → Configure providers → Anthropic**, enter your API key (stored in the keyring).
2. Start a **new chat**. Switching inside a running chat would send the whole conversation so far —
   every code snippet included — to the cloud.
3. Pick the cloud model in the model selector below the input (it shows `qwen3:8b`).
4. Raise the context limit for the cloud model: **Settings → App → configuration editor →
   Goose Context Limit**, e.g. `200000` — check the model’s real context size. The value from Step 1
   applies to every provider: left at `32768`, goose would compact a Claude session after ~26k tokens.
5. **Afterwards switch back:** Ollama in the model selector, *Goose Context Limit* back to `32768`,
   a new chat. `python3 scripts/check_setup.py` must show `provider: ollama` again.

### goose CLI

Environment variables override the config — for one session, nothing to switch back
([environment variables](https://goose-docs.ai/docs/guides/environment-variables)):

```bash
GOOSE_PROVIDER=anthropic GOOSE_MODEL=<claude-model> GOOSE_CONTEXT_LIMIT=200000 goose session
```

`<claude-model>`: one of the models `goose configure` lists for Anthropic. The API key is set once
with `goose configure` → Configure Providers → Anthropic. The next plain `goose session` is local again.

---

## Test the server without goose

The MCP Inspector (needs Node.js) lets you call the tools by hand:

```bash
npx @modelcontextprotocol/inspector .venv/bin/python mcp_server.py
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Failed to start extension 'local-code-rag'` | wrong path, or system Python instead of the venv | re-run `scripts/goose_extension.py`, copy the command again |
| `ModuleNotFoundError: chromadb` / `mcp` in the extension log | command uses the system Python | use `.venv/bin/python` |
| Tool returns `No index for embedding model …` | nothing indexed yet | `python3 index.py ../generated_kotlin` |
| Tool returns `Ollama not reachable` | Ollama stopped | `sudo systemctl start ollama` |
| goose answers without calling the tool | small model skipped the tool | say *"Search the code index …"*, add `.goosehints` |
| Extension missing in a running chat | extensions load at session start | start a new chat |
| Cloud model compacts after a few thousand tokens | `GOOSE_CONTEXT_LIMIT` still at the Ollama value | raise it for the cloud session (4.8) |
| Setup check fails with `provider: anthropic` | still switched to the cloud model | switch back to Ollama (4.8) |
