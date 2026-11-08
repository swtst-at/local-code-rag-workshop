# Step 6 — Exercises

**In the workshop: Exercise 1.** Exercises 2–4 are optional take-home experiments for tuning the RAG
to your own codebase — they change *how it works*, not how you use it.

| # | Exercise | Time | Needs |
|---|----------|------|-------|
| 1 | [Let goose write a new test](#exercise-1--let-goose-write-a-new-test) — **workshop** | 20–25 min | JDK 23+, Maven (Chrome optional) |
| 2 | [Chunk size](#exercise-2--chunk-size) | 10 min | — |
| 3 | [Generic vs. structure-aware chunking](#exercise-3--generic-vs-structure-aware-chunking) | 10 min | — |
| 4 | [Another embedding model](#exercise-4--another-embedding-model) | 10 min | `ollama pull qwen3-embedding:0.6b` (0.6 GB) |

---

## Exercise 1 — Let goose write a new test

The demo project tests Wikipedia. So far it searches for an exact title, which jumps straight to the
article. Your agent adds a test for the **search results page**: page object, step definitions, scenario —
**in the style of the existing code**.

This is where RAG pays off: the project has conventions a model cannot guess. It has to look them up.

### Setup

```bash
cd ../generated_kotlin            # or ../generated_java
git checkout -b exercise          # easy reset later
mvn -q test-compile               # must be green before you start
```

In goose:

- **Working directory:** the demo project (desktop: choose the folder for the session; CLI: start `goose session` there)
- **Extensions:** `local-code-rag` **and** `Developer` on — goose needs to write files and run Maven
- The index must match the code: `python3 index.py ../generated_kotlin` (from the workshop repo)

### The prompt

Copy it as is — the scenario text is fixed so the result can be checked automatically:

```
Add this scenario to src/test/resources/features/wikipedia.feature and implement it:

  @search
  Scenario: WIK-03 [wikipedia]
    Given the start page is loaded
    When the user searches for "selenium webdriver page object"
    Then at least 1 search result is shown
    When search result 1 is opened
    Then the article header is not empty

Before writing code, use search_code to find how page objects, step definitions and scenario names
are written in this project, and follow exactly the same patterns.
Search results on Wikipedia are in "li.mw-search-result", the title link in ".mw-search-result-heading a".
When done, run:
mvn -q test -Dcucumber.execution.dry-run=true -Dcucumber.filter.tags=@search -DbaseUrl=https://www.wikipedia.org
```

Java project: the scenario name is `[WIK-03 [wikipedia]` — see the checklist below.

### Check the result

**1. Dry run — no browser needed.** Cucumber checks that every step has exactly one matching step definition:

```bash
mvn -q test -Dcucumber.execution.dry-run=true -Dcucumber.filter.tags=@search -DbaseUrl=https://www.wikipedia.org
```

Green = compiles and all steps are implemented. `UndefinedStepException` = a step is missing.

**2. Real run — needs Chrome:**

```bash
mvn test -Dbrowser=chrome -Dheadless=true -DbaseUrl=https://www.wikipedia.org -Dcucumber.filter.tags=@search
```

**3. Conventions — did the agent find them?**

| Convention | Kotlin | Java |
|------------|--------|------|
| Page object base class | extends `MainPage(session)` | extends `MainPage`, `super(session)` |
| Navigation returns the next page | `fun …(): WikipediaSearchResultPage` | `public WikiPediaSearchresultPage …()` |
| Step definitions | lambdas in `init { }` of a class extending `AbstractStepDefs` | lambdas in the constructor, see trap 2 |
| Current page in steps | `getPage(X::class)` | `getPage(X.class)` |
| Assertions | AssertJ `assertThat` | AssertJ `assertThat` |
| **Scenario name** | `WIK-03 [wikipedia]` | **`[WIK-03 [wikipedia]`** — leading bracket |
| Existing search page? | no — create one | **yes** — `WikiPediaSearchresultPage` exists, extend it |

### Watch the agent

Note it down — we compare in the group:

- Did goose call `search_code` **before** writing code? With which queries?
- Did it reuse existing code (e.g. the Java search page) or duplicate it?
- How many attempts until the dry run was green?
- How long did it take on your machine?

### Stuck after 15 minutes? Try a cloud model

Small local models often struggle with a task across several files. Repeat it in a **new chat** with a
cloud model, as described in [Step 4.8](04-connect-goose.md#48-when-the-local-model-is-not-enough).
The demo project is public, so sending it to a cloud provider is fine here — with company code it
would not be. Compare in the group: attempts, time, and how well the conventions were followed.

### Traps — open only when stuck

<details>
<summary>Trap 1 (Kotlin): <code>Cannot infer type for this parameter</code> / <code>Unresolved reference 'sendKeys'</code></summary>

Selenium 4.41 has nullability annotations. The obvious Kotlin code
`wdwait.until(ExpectedConditions.presenceOfElementLocated(…)).sendKeys(…)` does **not** compile.
The project already has a workaround in `WikipediaStartPage.searchFor` — `wdwait.until { driver -> requireNotNull(…) }`.
Ask goose: *"Search the code for how searchFor waits for the search input and use the same pattern."*
</details>

<details>
<summary>Trap 2 (Java): <code>AmbiguousComponentResolutionException … AbstractStepDefs</code></summary>

A new step class (e.g. `SearchSteps.java`) breaks the dependency injection: cucumber-java8 tries to
create every `En` class in the glue package — including the **abstract** `AbstractStepDefs`.
With one subclass, picocontainer quietly picks it; with two, it cannot decide.

Two ways out:
- put the new steps into the existing `WikipediaSteps.java` (what the reference solution does), or
- make the base class concrete: `public class AbstractStepDefs` instead of `public abstract class` —
  the Kotlin project does exactly that (`open class`).
</details>

<details>
<summary>Trap 3: dry run green, real run fails at the scenario name</summary>

Kotlin extracts the test id with `^(.*) \[` and **fails** for a wrong name; Java uses `^\[(.*?) `.
Compare with the existing scenarios in `wikipedia.feature`.
</details>

### Reference solution

`exercises/01-search-results/solution-kotlin/` and `solution-java/` — the changed and new files,
with the same paths as in the demo project. Both pass the dry run against the unmodified demo projects.

```bash
diff -ru ../local-code-rag-workshop/exercises/01-search-results/solution-kotlin/src src
```

The selectors follow what the Java project already uses. The live run against Wikipedia depends on
Wikipedia's current HTML and search behaviour — if the search jumps straight to an article, use a
less specific search term.

### Reset

```bash
git checkout . && git clean -fd     # in the demo project
git checkout main
```

If you indexed the changed project, re-index after the reset.

---

## Take home: tune the RAG

For your own codebase. Measure every change with the golden set from
[Step 5](05-test-your-rag.md#take-home-measure-it) — `eval_retrieval.py` with the same environment variable.

## Exercise 2 — Chunk size

```bash
MAX_CHUNK_CHARS=500 python3 index.py --show-chunks ../generated_kotlin/src/test/kotlin/at/some/test/stepdefinitions/Hooks.kt
```

Rebuild the index with 500, ask the questions from Step 3 again (`search.py`), compare the ranking
with 1200. Which questions get better, which worse? Go back with `MAX_CHUNK_CHARS=1200 … --force`.

## Exercise 3 — Generic vs. structure-aware chunking

```bash
CHUNKER=generic python3 index.py ../generated_kotlin
CHUNKER=generic python3 search.py "Which step definition checks that the searchbar is visible?"
python3 search.py "Which step definition checks that the searchbar is visible?"
```

The generic index lives in its own collection, so both can be compared side by side.
Look at the chunk boundaries with `CHUNKER=generic python3 index.py --show-chunks …`.

## Exercise 4 — Another embedding model

```bash
ollama pull qwen3-embedding:0.6b    # the default tag is the 8B model, 4.7 GB
EMBED_MODEL=qwen3-embedding:0.6b python3 index.py ../generated_kotlin
EMBED_MODEL=qwen3-embedding:0.6b python3 search.py "How is the browser started?"
python3 search.py "How is the browser started?"
```

"Browser started" does not appear in the code — which model finds `createWebDriver` anyway?
Step 5 turns this comparison into numbers.
