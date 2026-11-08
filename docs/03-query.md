# Step 3 — Ask questions

Goal: get answers about the code — and understand where good and bad answers come from.

```
 question ──► embed ──► top-k chunks ──► prompt ──► qwen3:8b ──► answer with sources
            └──────── R: retrieval ───────┘         └──── G: generation ────┘
```

You will:

1. Look at **retrieval alone** — no LLM
2. Ask questions in the **terminal**
3. Learn the knobs that change answer quality

Prerequisites: Step 2 done, venv active (`source .venv/bin/activate`).

---

## 3.1 Retrieval first

```bash
python3 search.py "Which step definition checks that the searchbar is visible?"
```

```
🔍 Which step definition checks that the searchbar is visible?   [nomic-embed-text]

 1. 0.712 ██████████████       generated_kotlin/src/test/kotlin/…/WikipediaSteps.kt:7-22   class WikipediaSteps, Then("the searchbar is visible") …
 2. 0.688 ██████████████       generated_java/src/test/java/…/WikipediaSteps.java:10-35    class WikipediaSteps, …
 …
```

| Option | |
|--------|---|
| `-k 8` | number of results |
| `--code` | print the code of every hit |

(Example output — your scores and order will differ.)

The score is the **cosine similarity** between the question and the chunk (1.0 = same direction).
It is useful to *compare* hits for one question — the absolute value means little.

> **Rule of thumb:** if the right code is not in the top results, no LLM can answer correctly.
> Fix retrieval first — chunking, wording, `k`, embedding model.

---

## 3.2 Ask in the terminal

```bash
python3 ask.py "Which step definition checks that the searchbar is visible?"
```

The answer is streamed, followed by the sources and some statistics (example):

```
🔒 qwen3:8b · 5 chunks

The step "the searchbar is visible" is implemented in WikipediaSteps [1] …

Sources
  [1] generated_kotlin/src/test/kotlin/…/WikipediaSteps.kt:7-22  class WikipediaSteps … · score 0.712
  …
⏱ 9.3s · prompt 2104 tokens · answer 118 tokens at 13.7 tok/s
```

| Option | |
|--------|---|
| `-k 3` | fewer chunks → shorter prompt, faster, but maybe missing context |
| `--think` | let qwen3 reason before answering (≈ 3× slower) |
| `--show-prompt` | print exactly what the LLM receives |
| `--prompt basic` | the first version of the system prompt — compare (see 3.4) |
| `--model qwen3:4b` | another Ollama model |

Run `--show-prompt` once. There is no magic: a system prompt with rules, the retrieved chunks,
your question. That's all the model knows about your code.

---

## 3.3 What changes the answer?

| Knob | Effect | Try |
|------|--------|-----|
| **k** (chunks) | more context vs. more noise and a longer prompt | `-k 2` vs `-k 10` |
| **Thinking** | better on multi-step questions, much slower | `--think` |
| **Question wording** | embeddings match *meaning*, but the code's vocabulary still helps | "browser" vs "WebDriver" |
| **Chunking** | decides what *can* be found (Step 2) | `CHUNKER=generic` index |
| **Embedding model** | decides how well meaning is matched (Step 5) | `EMBED_MODEL=qwen3-embedding` |

### Good questions to try

| Question | What it tests |
|----------|---------------|
| Which step definition checks that the searchbar is visible? | exact lookup across Gherkin and code |
| How is the WebDriver created for Firefox? | finding the right factory among many similar ones |
| What happens after a scenario has finished? | hooks, cleanup, screenshots |
| Which scenarios use more than one user? | Gherkin only — exists in the Kotlin repo only |
| How does the DevicePool work? | exists in the Kotlin repo only — what does the Java index answer? |
| How do I add a new page object? | needs several chunks — compare `-k 3` and `-k 10` |
| What does the login step do? | **there is no login step** — does the model admit it? |

The last one matters: a good RAG setup says *"not in the code"* instead of inventing an answer.

---

## 3.4 The system prompt matters

Ask the login question with both prompt versions:

```bash
python3 ask.py "What does the login step do?" --prompt basic
python3 ask.py "What does the login step do?"                    # strict, the default
```

Typical answer with **basic**:

> The code excerpts provided do not include a "login step." To determine what the login step does,
> you would need to search for step definitions related to "login" in the codebase, such as files
> named `LoginSteps.kt` or similar. …

Honest — no login step is invented. But look closer:

| Problem | Caused by the basic prompt |
|---------|----------------------------|
| "excerpts" — internal jargon the user does not understand | the prompt calls the chunks "excerpts" |
| `LoginSteps.kt` — a file that does not exist | the rule *"suggest what to search for instead"* invites guessing |

The **strict** prompt (`rag/answer.py`) talks about "the searched code", forbids guessing file names,
and stops when the answer is not found.

It also says: *never claim that something does not exist*. The model only sees the top-k search
results, not the repository. "I could not find it in the searched code" is honest;
"there is no login step" is a claim the model cannot verify — in a small repo it happens to be true,
in a large one it may not be.

Also note: vector search **always** returns k results, even when nothing fits —
`python3 search.py "login step"` shows 5 hits with scores as high as for a real match.
Deciding "not there" is the LLM's job, and only the prompt tells it how.

---

## Configuration

| Variable | Default | |
|----------|---------|---|
| `LLM_MODEL` | `qwen3:8b` | model that writes the answers |
| `LLM_THINK` | `false` | reasoning phase on/off |
| `TOP_K` | `5` | chunks per question |
| `PROMPT` | `strict` | system prompt variant (`strict`, `basic`) |
| `EMBED_MODEL` | `nomic-embed-text` | must match the model used for indexing |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No index for embedding model …` | run `python3 index.py <repo>` with the same `EMBED_MODEL` |
| First answer takes long | the model is loaded into memory first; later answers are faster |
| Answer ignores the code / invents things | check `search.py` — is the right code retrieved? Try `--show-prompt` |
