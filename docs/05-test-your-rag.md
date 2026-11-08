# Step 5 — Test your RAG

## In the workshop: can I trust the answer?

Four checks before you use an answer — from real test runs with `qwen3:8b` on `generated_kotlin`:

| Check | Why |
|-------|-----|
| **Check the sources** — is the file you expect among them? | “How is the browser chosen from the system properties?” got a confident answer five times in a row — built from the wrong files. The search never returned `DriverFactory.kt` or `DriverContext.kt`. |
| **“Not found” is a good answer** | With the strict prompt the model admitted missing answers (login step, passwords, REST API) in every run. With the basic prompt it once invented `LoginSteps.kt`. |
| **“However, … is not shown” is a warning** | Three of those five wrong answers ended like this — the context was not enough. Ask again with the code’s words, or let goose read the file. |
| **Ask twice** | Retrieval is deterministic, the answer is not. Clearly different answers → read the code yourself. |

The rest of this page is **take-home**: how to turn these checks into numbers for your own codebase.

---

## Take home: measure it

Goal: replace “the answer looked good” with numbers you can compare and repeat.

RAG has two halves, and they need two different kinds of tests:

| | Retrieval | Generation |
|---|---|---|
| What | question → top-k chunks | chunks + prompt → answer |
| Deterministic? | **yes** — same index, same question, same result | **no** — the same question can get a different answer |
| How to test | exact assertions: is the right file in the top k? | statistics: how often does the answer pass, over several runs? |
| Script | `eval_retrieval.py` — seconds, no LLM | `eval_answers.py` — minutes |

You will:

1. Look at the golden question set
2. Measure retrieval
3. Measure answers — and see the non-determinism in numbers
4. Decide what to change based on the numbers — and, optionally, compare setups

Prerequisites: index built (Step 2), venv active. Run `pip install -r requirements.txt` once more —
Step 5 reads YAML files.

---

## 5.1 Golden questions

`eval/golden_kotlin.yaml` and `eval/golden_java.yaml` hold the test cases — questions with the
file where the answer lives:

```yaml
repo: generated_kotlin

questions:
  - id: K02
    question: How is the WebDriver created for Firefox?
    expect: [FirefoxWebDriverFactory.kt]

  - id: K12                                # vocabulary gap: these words are not in the code
    question: How is the browser started before a test?
    expect: [DriverFactory.kt, DriverContext.kt, WebDriverSession.kt, Hooks.kt]

  - id: N01                                # negative: the answer is not in the code
    question: What does the login step do?
    expect: []
```

| Field | Meaning |
|-------|---------|
| `expect` | exact file names (or path endings like `strategy/DriverContext.kt`); a hit if **any** of them is retrieved |
| `expect: []` | **negative question** — the correct answer is “not in the code” |
| `mention` | optional: words a correct answer must contain (default: the expected file and class names) |

Each set has 12 positive and 3 negative questions. The positive ones mix exact lookups,
questions that need the right file among many similar ones (the WebDriver factories), and
vocabulary-gap questions whose words do not appear in the code.

> For testers this is a familiar idea: a golden set is a **regression test suite** for your RAG.
> Run it after every change — a new embedding model, a different chunk size, a new prompt.
> Add your own questions; the ones from your real work are the best ones.

---

## 5.2 Retrieval eval

```bash
python3 eval_retrieval.py
```

It picks the golden set for the repository in your index. Format of the output
(your ranks and numbers will differ):

```
Retrieval eval · golden_kotlin.yaml · nomic-embed-text · code__nomic-embed-text · repo generated_kotlin · top 5

  K01     2  Which step definition checks that the searchbar is visible?
  K02     1  How is the WebDriver created for Firefox?
  …
  K12  miss  How is the browser started before a test?

Recall@1 … · Recall@3 … · Recall@5 … · MRR …
12 questions · missed: K12 · 3 negative questions skipped — see eval_answers.py
```

| Metric | Meaning |
|--------|---------|
| **rank** | position of the first expected file among the results |
| **Recall@k** | share of questions whose expected file is in the top k. Recall@5 is what the LLM sees with `TOP_K=5` |
| **MRR** | mean reciprocal rank — 1 / rank of the first hit, averaged (rank 1 → 1.0, rank 2 → 0.5, miss → 0). Rewards finding it *early* |

`-v` shows what was retrieved instead, for every question not found at rank 1.
`--only K02,K12` runs single questions.

### Optional, after the workshop: compare setups — change one thing at a time

Not part of the workshop timeline. For when you want to tune the RAG for your own codebase.

| Change | Command | Note |
|--------|---------|------|
| Embedding model | `ollama pull qwen3-embedding:0.6b` · `EMBED_MODEL=qwen3-embedding:0.6b python3 index.py ../generated_kotlin` · `EMBED_MODEL=qwen3-embedding:0.6b python3 eval_retrieval.py` | separate collection, the original stays |
| Generic chunker | `CHUNKER=generic python3 index.py ../generated_kotlin` · `CHUNKER=generic python3 eval_retrieval.py` | separate collection, the original stays |
| Chunk size | `MAX_CHUNK_CHARS=500 python3 index.py ../generated_kotlin --force` · `python3 eval_retrieval.py` | **overwrites** the index — afterwards: `python3 index.py ../generated_kotlin --force` |

Write the numbers down side by side. With 12 questions, one question is 8 percentage points —
small differences are noise; look for clear ones.

---

## 5.3 Answer eval

```bash
python3 eval_answers.py                    # all 15 questions × 3 runs — several minutes
python3 eval_answers.py --only K01,K02,N01 --runs 5
```

Retrieval runs **once** per question; only the answer is generated again in every run.
Every difference between runs therefore comes from the LLM.

```
Answer eval · golden_kotlin.yaml · qwen3:8b · prompt strict · 3 runs × 15 questions

  K01  ✓✓✓  3/3  Which step definition checks that the searchbar is visible? (positive)
  N01  ✓✗✓  2/3  What does the login step do? (negative)
         run 2: FAIL — invents LoginSteps.kt · 11.8s
  …

Pass rate …/45 (…%) · same result in every run: … of 15 questions · … min
```

### The checks

Simple on purpose — every test needs an oracle, and this one is visible:

| Check | Fails when |
|-------|-----------|
| **No invented files** — every answer | it names a `.kt`, `.java` or `.feature` file that is not in the index |
| **Positive question** | it names none of the expected files or classes, or claims nothing was found |
| **Negative question** | it does not say that it could not find the answer |

The checks are heuristics. A failing answer is printed — read it before you trust the number.
`-v` prints every answer.

> **Test the oracle, too.** In the first real run, three questions failed in *every* run —
> and the answers were correct:
>
> | Question | Answer | Why it failed |
> |----------|--------|---------------|
> | Where are screenshots taken …? | “… in the `afterScenario` function …” | named the method, not the file → `mention: [Hooks, afterScenario]` |
> | How are passwords stored? | “The searched code does not provide information …” | phrase not in the not-found list → added |
>
> And one bug in the other direction — a test that passed although it should not have:
> `DriverFactory.kt` matched `WebDriverFactory.kt` as a substring, so a wrong file counted as a hit.
> Now file names must match exactly, and answer terms as whole words.
>
> A question that fails **3/3 with the same answer** is more often a wrong oracle than a wrong model.
> A question that fails **1/3 or 2/3** is the model — that is the non-determinism you came to measure.

### Experiments

| Question | Command |
|----------|---------|
| Does the prompt matter? | `python3 eval_answers.py --prompt basic` vs. the default `strict` |
| Does thinking help? | `python3 eval_answers.py --think` |
| More context, better answers? | `python3 eval_answers.py -k 10` |
| Would a smaller model do? | `python3 eval_answers.py --model qwen3:4b` |

Use `--only` with a handful of questions and `--runs 5` to keep it short.

---

## 5.4 What the numbers tell you

| You see | Likely cause | Lever |
|---------|-------------|-------|
| Low Recall@5 | the right code is not retrieved | chunking, embedding model, question wording |
| Good Recall@5, low MRR | found, but too far down | chunk size, embedding model |
| Good retrieval, failing positive answers | the model does not use the chunks well | prompt, model, `k` |
| Failing negative questions | the model invents instead of admitting | prompt (Step 3.4) |
| Same question passes and fails | non-determinism | more runs; thinking; a stronger model |
| Misses only on vocabulary-gap questions | the code uses other words | embedding model; or ask with the code’s words |

**Fix retrieval first.** An answer can only be as good as the chunks it is built from.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Index holds 2 repositories` | pass `--set eval/golden_kotlin.yaml` or remove one repo (`index.py --remove …`) |
| `ModuleNotFoundError: yaml` | `pip install -r requirements.txt` |
| `No index for embedding model …` | build the index with the same `EMBED_MODEL` / `CHUNKER` first |
| Answer eval takes too long | `--only` a few questions, fewer `--runs`, or `--model qwen3:4b` |
| Your own repository | copy a golden file, set `repo:` to its folder name, write questions with known answers |
