# Step 2 — Index a codebase

Goal: turn a code repository into a local, searchable vector index.

```
 .kt / .java / .feature ──► chunks ──► embeddings (Ollama) ──► ChromaDB (./db)
```

You will:

1. Activate the Python environment
2. Get the demo repository
3. Look at how code is chunked
4. Build the index — and update it incrementally

---

## 2.1 Python environment

The venv and the embedding model were set up in Step 1 (sections 1.3 and 1.6).
In every new terminal, activate the venv again from the workshop repository:

```bash
source .venv/bin/activate          # the prompt shows (.venv)
```

---

## 2.2 Demo repository

**Pick one** — the language you are more at home with:

| Repository | Language | Files | Chunks |
|------------|----------|-------|--------|
| [secugrow/generated_kotlin](https://github.com/secugrow/generated_kotlin) | Kotlin | 39 `.kt` + 1 `.feature` | 85 |
| [secugrow/generated_java](https://github.com/secugrow/generated_java) | Java | 28 `.java` + 1 `.feature` | 52 |

Both are generated test-automation projects with Selenium, Appium and Cucumber — page objects,
WebDriver factories, step definitions, hooks. Small enough to index in seconds, realistic enough
to ask real questions.

```bash
git clone https://github.com/secugrow/generated_kotlin.git ../generated_kotlin
# or
git clone https://github.com/secugrow/generated_java.git ../generated_java
```

Why only one? Both projects contain the same features — the same step definitions exist in Kotlin
*and* Java. Indexed together, they compete for the same top places: with `k=5` you may get the
Kotlin version of a step and miss the Java one, and the answer is incomplete without anyone noticing.

You can index your own project too. The commands below use `generated_kotlin`; replace it with
`generated_java` if that is your choice.

### Which files are indexed?

Configured in `rag/config.py`:

```python
FILE_TYPES = {
    ".kt": "kotlin",
    ".java": "java",
    ".feature": "gherkin",
}
IGNORE_DIRS = {".git", ".gradle", ".idea", "build", "target", ...}
```

The language decides which chunker is used. Other file types work without changing code —
they use the **generic** chunker:

```bash
EXTRA_FILE_TYPES=".py,.ts,.xml" python3 index.py ../my-project
```

---

## 2.3 Chunking — look before you embed

An embedding turns a piece of text into a vector. The index can only find what the chunks contain,
so **how** we cut the code decides the quality of everything that follows.

| Chunks too big | Chunks too small | Cut at the wrong place |
|----------------|------------------|------------------------|
| One vector mixes many topics → "blurry" matches | Missing context → the snippet means nothing on its own | A function split in half → retrieval finds only one half |

Our strategy (`rag/chunking.py`):

| Language | Cut at |
|----------|--------|
| **Kotlin** | declarations (`class`, `fun`, `object`, …) |
| **Java** | declarations (`class`, `interface`, `enum`, `record`, methods, constructors) |
| both | Cucumber steps — lambda style `Given("…") { }` / `Given("…", () -> { })` and annotation style `@Given("…")` |
| **Gherkin** | one chunk per scenario, including its tags |
| **generic** | blank lines — knows nothing about the language |

For Kotlin and Java, doc comments and annotations stay with their declaration, `import` lines are
dropped, and small neighbours are merged up to `MAX_CHUNK_CHARS` (default 1200).
**Every chunk** gets a short header — file, package, class — so it still makes sense on its own.

See it for yourself (no Ollama needed):

```bash
python3 index.py --show-chunks ../generated_kotlin/src/test/resources/features/wikipedia.feature
python3 index.py --show-chunks ../generated_kotlin/src/test/kotlin/at/some/test/stepdefinitions/Hooks.kt
python3 index.py --show-chunks ../generated_java/src/test/java/io/secugrow/demo/stepdefinitions/Hooks.java
```

Compare with the generic chunker — what is missing?

```bash
CHUNKER=generic python3 index.py --show-chunks ../generated_java/src/test/java/io/secugrow/demo/stepdefinitions/Hooks.java
```

```
━━━ chunk 1/2 · lines 4-10 · 252 chars · Scenario: WIK-01 [wikipedia]
# File: wikipedia.feature
# Feature: [wikipedia] Example Feature

  @boris
  Scenario: WIK-01 [wikipedia]
    Given the start page is loaded
    ...
```

Experiment: `MAX_CHUNK_CHARS=400 python3 index.py --show-chunks …/Hooks.kt` — what changes?

---

## 2.4 Build the index

```bash
python3 index.py ../generated_kotlin
```

```
🔒 Local indexing — embeddings via Ollama (nomic-embed-text), nothing leaves this machine
📁 /home/you/repos/generated_kotlin
   40 files · 0 unchanged · 40 new/changed · 0 removed
✅ 85 chunks embedded in …s → ./db [code__nomic-embed-text]
```

```bash
python3 index.py --stats
```

Switching to the other repository:

```bash
python3 index.py --remove generated_kotlin
python3 index.py ../generated_java
```

Technically an index can hold several repositories — every chunk remembers its repository, and
updating one never touches the others. The search tools can then be limited with `--repo`.
For the workshop: keep one.

### Incremental updates

Run the same command again after changing code. Only what changed is embedded again:

| Situation | What happens |
|-----------|--------------|
| File unchanged (same SHA-256) | skipped |
| File changed | its old chunks are deleted, the new version is embedded |
| File deleted | its chunks are deleted |
| `--force` | this repository's part of the index is rebuilt |

Removing stale chunks matters: otherwise the index returns code that no longer exists —
and the LLM confidently explains it.

---

## What happens under the hood

### Embedding prefixes

Many embedding models are trained to distinguish *documents* from *questions*.
`nomic-embed-text` expects `search_document: ` before every chunk and `search_query: ` before every
question. Forgetting them silently lowers retrieval quality. `rag/ollama.py` adds them
automatically for the models we use:

| Model | Document prefix | Query prefix |
|-------|-----------------|--------------|
| `nomic-embed-text` | `search_document: ` | `search_query: ` |
| `embeddinggemma` | `title: none \| text: ` | `task: code retrieval \| query: ` |
| `qwen3-embedding` | — | `Instruct: … Query: ` |

### One collection per embedding model

Vectors from different models are not comparable — different sizes, different "meaning".
Each model gets its own collection (`code__nomic-embed-text`, `code__qwen3-embedding`, …).
That also lets you compare models later (Step 5):

```bash
ollama pull qwen3-embedding
EMBED_MODEL=qwen3-embedding python3 index.py ../generated_kotlin
```

### Batching

Chunks are sent to Ollama's `/api/embed` endpoint in batches of 32 — 85 chunks are 3 requests,
not 85.

### What is stored

| Field | Example | Used for |
|-------|---------|----------|
| document | header + code | what the LLM reads |
| `repo` | `generated_kotlin` | several repos in one index |
| `path` | `src/test/kotlin/…/Hooks.kt` | sources, incremental updates |
| `start_line` / `end_line` | `41` / `68` | precise references |
| `symbol` | `fun beforeScrenario` | readable results |
| `hash` | SHA-256 of the file | change detection |

---

## Configuration

| Variable | Default | |
|----------|---------|---|
| `EMBED_MODEL` | `nomic-embed-text` | embedding model |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `RAG_DB_PATH` | `./db` | where ChromaDB stores the index |
| `MAX_CHUNK_CHARS` | `1200` | target chunk size |
| `EXTRA_FILE_TYPES` | — | more extensions, e.g. `.py,.ts` (generic chunker) |
| `CHUNKER` | — | `generic` = ignore the language (separate collection, for comparison) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Model 'nomic-embed-text' is not installed` | `ollama pull nomic-embed-text` |
| `Ollama not reachable` | `sudo systemctl start ollama` |
| `ModuleNotFoundError: chromadb` | `source .venv/bin/activate` |
| `No .kt, .java, .feature files found` | check the path, or add types via `EXTRA_FILE_TYPES` |
| Results contain deleted code | run `python3 index.py <repo>` again, or `--force` |
