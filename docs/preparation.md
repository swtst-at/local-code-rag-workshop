# Preparation — before the workshop

Please do this **at home, not over conference Wi-Fi** — the models are several GB.
Plan about an hour, most of it downloads.

## 1. goose and Ollama

Work through [Step 1](01-setup-goose-ollama.md): install goose and Ollama, pull `qwen3:8b`
and `nomic-embed-text`, point goose at Ollama.

## 2. The workshop repository and one demo project

```bash
git clone https://github.com/swtst-at/local-code-rag-workshop.git
git clone https://github.com/secugrow/generated_kotlin.git   # or generated_java — pick one
cd local-code-rag-workshop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Both folders side by side, e.g. `~/workshop/local-code-rag-workshop` and `~/workshop/generated_kotlin`.
Kotlin or Java: take the language you know better — we work with one demo project per person.

## 3. Java and Maven — for the main exercise

**JDK 23 or newer** and **Maven** — the demo projects target Java 23.
Download the Maven dependencies at home too:

```bash
cd ../generated_kotlin && mvn -q test-compile && cd -
```

Chrome is only needed to run the tests for real; the exercise can be checked without a browser.

## 4. Setup check

```bash
python3 scripts/check_setup.py
```

Everything should be green. If not, the troubleshooting table in [Step 1](01-setup-goose-ollama.md#troubleshooting)
covers the usual causes.

## On the morning of the workshop

The repository may still change until then:

```bash
cd local-code-rag-workshop && git pull && pip install -r requirements.txt
```

## Hardware

| Machine | Expectation |
|---------|-------------|
| GPU / Apple Silicon / iGPU with ≥ 16 GB shared RAM | Comfortable |
| CPU only, 16 GB RAM | Works, but slow — use the smaller fallback model from Step 1 |
| < 16 GB RAM | Not recommended |

| Platform | |
|----------|---|
| Linux (Ubuntu) | reference platform |
| macOS | works with the notes in Step 1 |
| Windows | follow the [Windows cheat sheet](Windows_Cheat_Sheet.pdf) — not yet tested end to end |
