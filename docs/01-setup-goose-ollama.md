# Step 1 — Set up goose with a local LLM

Goal: goose runs as an agent, uses tools, and talks **only** to a model on your machine.

You will:

1. Install or update **goose** (CLI, optionally the desktop app)
2. Install or update **Ollama** and tune it for agent use
3. Pull the models — one with **tool calling**, one for embeddings
4. Point goose at Ollama and verify it works
5. Set up the **Python environment** and run the setup check

Reference platform: Ubuntu. macOS notes are included where things differ.

---

## 1.1 Install or update goose

goose now lives under the Agentic AI Foundation: **`github.com/aaif-goose/goose`**.
Old `block/goose` URLs in scripts or bookmarks are outdated.

### Find out what you already have

```bash
which -a goose
goose --version
ls -l ~/.local/bin/goose 2>/dev/null      # CLI via install script
dpkg -l | grep -i goose                   # desktop app (.deb)
brew list 2>/dev/null | grep -i goose     # Homebrew
```

Typical result on Ubuntu:

| Path | What it is |
|------|------------|
| `~/.local/bin/goose` | **CLI**, installed via the install script |
| `/usr/bin/goose` (and `/bin/goose`, a symlink) | **Desktop app** from the `.deb` package |

`~/.local/bin` usually comes first in `PATH`, so `goose` in a terminal starts the CLI.
If `~/.local/bin/goose` shows up several times, the directory is in your `PATH` several times
(each install-script run may append it again) — harmless, but you can clean up `~/.bashrc` / `~/.profile`.

CLI and desktop app share the same configuration in `~/.config/goose/`. Keep both on similar versions.

### Install / update the CLI

```bash
curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash
```

`CONFIGURE=false` skips the interactive setup — we configure goose ourselves in 1.4.

For an existing install, `goose update` works too. If it fails with
**`Text file busy (os error 26)`**, the running binary cannot overwrite itself. Move it aside first:

```bash
pgrep -a goose                                  # close any running goose sessions
mv ~/.local/bin/goose ~/.local/bin/goose.old    # renaming a running binary is allowed
curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash
goose --version
rm ~/.local/bin/goose.old
```

macOS: `brew install block-goose-cli` / `brew upgrade block-goose-cli`.

### Install / update the desktop app (optional)

The desktop app is useful if you prefer a GUI. Close it, then:

```bash
curl -s https://api.github.com/repos/aaif-goose/goose/releases/latest \
  | grep browser_download_url | grep '\.deb'
cd /tmp && wget <url-from-above>
sudo apt install ./goose_*.deb
```

Take the **regular** build, not the Vulkan one. The Vulkan build only accelerates goose's *built-in*
model runner. We run models in Ollama, which handles the GPU on its own.

> The note `Download is performed unsandboxed as root …` from `apt` is harmless.

---

## 1.2 Install or update Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh    # installs or updates
ollama --version
systemctl status ollama --no-pager
```

macOS: install or update the Ollama app from [ollama.com](https://ollama.com).

### Tune Ollama for agent use

Two settings matter. On Linux, Ollama runs as a systemd service, so set them in an override:

```bash
sudo systemctl edit ollama
```

Add between the comment lines:

```ini
[Service]
Environment="OLLAMA_CONTEXT_LENGTH=32768"
Environment="OLLAMA_IGPU_ENABLE=1"
```

```bash
sudo systemctl restart ollama
systemctl show ollama | grep -o 'OLLAMA_[A-Z_]*=[^ ]*'
```

**`OLLAMA_CONTEXT_LENGTH`** — goose sends its system prompt plus all tool definitions with every
request; that is several thousand tokens before you have typed anything. Without a GPU, Ollama falls
back to a **4096-token** context and silently truncates. The model then ignores tools or `.goosehints`.
Use `32768` if you have ≥ 16 GB (V)RAM, otherwise `16384`. Set it explicitly — don't rely on the
automatic value.

**`OLLAMA_IGPU_ENABLE`** — integrated GPUs (e.g. AMD Radeon 780M) are ignored by default. The log tells you:

```bash
journalctl -u ollama -n 50 --no-pager | grep -iE "inference compute|vram|igpu"
```

| Log line | Meaning |
|----------|---------|
| `dropping integrated GPU; to enable, set OLLAMA_IGPU_ENABLE=1` | iGPU found but disabled → set the variable |
| `inference compute … library=Vulkan … type=iGPU` | iGPU in use ✅ |
| `inference compute … library=cpu` only | CPU only — works, just slower |

macOS: set variables with `launchctl setenv OLLAMA_CONTEXT_LENGTH 32768`, then restart the Ollama app.
Apple Silicon GPUs are used automatically.

---

## 1.3 Pull the models

goose relies on **tool calling**. A model without it can only chat — the agent cannot read files,
run commands or use our RAG tool.

```bash
ollama pull qwen3:8b            # ~5 GB, the workshop default
ollama pull nomic-embed-text    # ~270 MB, turns code into vectors (Step 2)
```

| Your machine | Model |
|--------------|-------|
| ≥ 16 GB (V)RAM / Apple Silicon / iGPU | `qwen3:8b` |
| ≥ 24 GB (V)RAM | `qwen3:14b` (better tool use, slower) |
| CPU only / slow machine | `qwen3:4b` (fallback) |

### Measure your speed

```bash
ollama run qwen3:8b --verbose "Explain RAG in three sentences"
ollama run qwen3:8b --verbose --think=false "Explain RAG in three sentences"
ollama ps
```

- **eval rate** — how fast the answer is generated (tokens/s)
- **prompt eval rate** — how fast the input is read; this dominates with goose's large prompts
- **PROCESSOR** in `ollama ps` — `100% GPU`, `100% CPU`, or a split

`qwen3` *thinks* before answering by default. That improves multi-step reasoning, but costs time:

Reference values (Framework 13, AMD Radeon 780M iGPU via Vulkan, `qwen3:8b`):

| | Tokens generated | Total time | Eval rate |
|---|---|---|---|
| Thinking on | 295 | 25.4 s | 13.7 tok/s |
| Thinking off (`--think=false`) | 119 | 8.9 s | 13.8 tok/s |

Same generation speed, a third of the time — thinking simply produces more tokens.
For agent work in goose we keep thinking **on**; for plain RAG answers we will turn it **off** later.

---

## 1.4 Point goose at Ollama

```bash
goose configure
```

→ **Configure Providers** → **Ollama** → host `http://localhost:11434` → model `qwen3:8b`

### Desktop app

On first start (or after a big update) the desktop app shows a setup screen with two choices:

| Card | What it really means |
|------|----------------------|
| *Use a local model* | goose's **built-in** model runner — downloads separate models from HuggingFace, **not** Ollama |
| *Connect to a provider* | choose a provider — **Ollama is one of them** and runs locally |

> [!WARNING]
> Choose **Connect to a provider → Ollama**, even though "local model" sounds right.
> The built-in runner would download another multi-GB model next to the one in Ollama,
> and our RAG uses Ollama anyway.

Then: host `http://localhost:11434`, model `qwen3:8b`.
Later changes: **Settings → Configure Provider → Ollama**.

**UI in another language?** goose follows the system language. Switch it to English so the labels
match this guide: **Settings → App → Language**. (Alternative: start the app with the environment
variable `GOOSE_LOCALE=en`.)

### Tell goose the real context size

goose does not know how much context Ollama really serves. Without further information it assumes
**128k tokens** and compacts the conversation at 80 % of that — around 100k tokens
([smart context management](https://goose-docs.ai/docs/guides/sessions/smart-context-management)).
Ollama only serves what you set in 1.2, e.g. 32k. Between the two, Ollama **silently cuts off the
start of the conversation** — system prompt, tool descriptions, your first instructions. The model
then forgets rules or tools, without any error message.

Tell goose the real value — the same as `OLLAMA_CONTEXT_LENGTH`:

```bash
printf '\nGOOSE_CONTEXT_LIMIT: 32768\n' >> ~/.config/goose/config.yaml
```

(`printf` with a leading line break: if the file does not end with one, `echo` would glue the line
to the last line and break the YAML.) CLI and desktop app both read it; the desktop app shows it under
**Settings → App → configuration editor** as *Goose Context Limit*.

Check it in a chat: the context indicator shows **`…/33k`** (32,768 rounded) — but only **after
the first message**. An empty new chat shows the default `…/128k`.

> [!NOTE]
> Setting up a provider again in the desktop app can rewrite the config and drop this line.
> Afterwards, check that it is still there (`grep GOOSE_CONTEXT_LIMIT ~/.config/goose/config.yaml`).
>
> The value applies to **every** provider — also to a cloud model you switch to. See Step 4,
> “When the local model is not enough”.

### Verify that nothing goes to the cloud

```bash
grep -n -E "active_provider|GOOSE_PROVIDER|GOOSE_CONTEXT_LIMIT|OLLAMA_HOST|^providers:|^  [a-z_]+:$|^    model:" ~/.config/goose/config.yaml
```

Recent goose versions store the active provider and keep one model **per provider**:

```yaml
OLLAMA_HOST: localhost        # or http://localhost:11434
GOOSE_CONTEXT_LIMIT: 32768
providers:
  anthropic:
    model: claude-sonnet-4-6  # other providers may stay configured…
  ollama:
    model: qwen3:8b
active_provider: ollama       # …what counts is the active one
```

Older versions use `GOOSE_PROVIDER: ollama` and `GOOSE_MODEL: qwen3:8b` instead.

If the active provider is anything other than `ollama`, **code you share with goose leaves your machine.**
The goose session banner shows it as well: `● new session · ollama qwen3:8b`.

### Remove stale extensions

Extensions that cannot start produce a warning at session start
(`Failed to start extension '…'`). Find and delete them in the config:

```bash
grep -n -A6 "^extensions:" ~/.config/goose/config.yaml
grep -rn -i "localhost:" ~/.config/goose/
```

Delete the whole block of the broken extension, or set `enabled: false`.

---

## 1.5 Smoke test

```bash
mkdir -p ~/tmp/goosetest && cd ~/tmp/goosetest && touch a.txt b.kt
goose session
```

```
> List the files in the current directory
```

✅ **Pass:** goose calls a tool (e.g. `tree` or `shell`) and lists `a.txt` and `b.kt`.

❌ **Fail:** the model only *tells* you to run `ls` → no tool calling. Check the model and the context size.

Ask a second question in the same session (`What is in b.kt?`). It should be noticeably faster:
the first request pays for reading goose's ~6k-token system prompt, later ones reuse Ollama's prompt cache.

> **Expect the first answer to take about a minute** on an iGPU (54 s measured on the reference
> machine), longer on CPU only. It is not hanging.

---

## 1.6 Python environment and setup check

The RAG scripts need a few Python packages. They go into a **venv** (virtual environment) — a
project-local Python installation in `.venv/`, comparable to every Maven project having its own
dependencies; `requirements.txt` plays the role of the `pom.xml`. Recent Ubuntu versions refuse
`pip install` into the system Python, so a venv is the clean way.

From the root of the workshop repository:

```bash
python3 -m venv .venv
source .venv/bin/activate          # every new terminal: activate again — the prompt shows (.venv)
pip install -r requirements.txt
```

Ubuntu: if `venv` is missing → `sudo apt install python3-venv`.

Then run the setup check — with the venv active:

```bash
python3 scripts/check_setup.py
```

Everything should be green. Warnings are optional improvements; the Java and Maven checks only
matter for the exercise in Step 6.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Text file busy (os error 26)` on `goose update` | binary replaces itself while running | move it aside, reinstall (1.1) |
| `goose --version` still shows the old version | several goose binaries in `PATH` | `which -a goose` |
| `Ollama not reachable` | service not running | `sudo systemctl start ollama` |
| goose ignores tools / answers only with text | model without tool calling, or context too small | `qwen3:8b`, `OLLAMA_CONTEXT_LENGTH` (1.2) |
| `ollama ps` shows `100% CPU` despite a GPU | iGPU disabled | `OLLAMA_IGPU_ENABLE=1` (1.2) |
| `Failed to start extension` at session start | stale extension in the config | remove it (1.4) |
| Very slow first answer | large system prompt, thinking | expected; second answer is faster |
| `chromadb not found — is the venv active?` | venv not created or not activated | `source .venv/bin/activate` (1.6) |
| Context indicator shows `…/128k` | empty chat (shows the default) or `GOOSE_CONTEXT_LIMIT` missing | send a message first; check the config (1.4) |
| goose forgets rules or stops using tools in a long session | conversation longer than Ollama's context, the start is cut off | `GOOSE_CONTEXT_LIMIT` (1.4); start a new chat per task |
