#!/usr/bin/env python3
"""
Workshop setup check — verifies goose, Ollama, the models, the goose config and Python.

Usage (from the repository root, with the venv active):
    python3 scripts/check_setup.py
    WORKSHOP_MODEL=qwen3:4b python3 scripts/check_setup.py   # fallback model

Only uses the Python standard library, so it runs before any `pip install`.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MODEL = os.environ.get("WORKSHOP_MODEL", "qwen3:8b")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
MIN_CONTEXT = 16384
GOOSE_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "goose" / "config.yaml"

results = {"ok": 0, "warn": 0, "fail": 0}


def ok(msg):
    results["ok"] += 1
    print(f"  ✅ {msg}")


def warn(msg, hint=None):
    results["warn"] += 1
    print(f"  ⚠️  {msg}")
    if hint:
        print(f"     → {hint}")


def info(msg):
    print(f"  ℹ️  {msg}")


def fail(msg, hint=None):
    results["fail"] += 1
    print(f"  ❌ {msg}")
    if hint:
        print(f"     → {hint}")


def section(title):
    print(f"\n{title}")


def http_json(path, payload=None, timeout=5):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ── goose ─────────────────────────────────────────────────────────────────────
def check_goose():
    section("goose")
    found = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(d) / "goose"
        if p.is_file() and os.access(p, os.X_OK):
            real = p.resolve()
            if real not in found:
                found.append(real)

    if not found:
        fail("goose not found in PATH", "see docs/01-setup-goose-ollama.md, section 1.1")
        return

    try:
        out = subprocess.run(["goose", "--version"], capture_output=True, text=True, timeout=15)
        version = (out.stdout or out.stderr).strip()
        ok(f"goose {version} ({shutil.which('goose')})")
    except Exception as e:
        fail(f"goose found but '--version' failed: {e}")

    # The desktop app (.deb) puts a launcher in /usr/bin that resolves to /usr/lib/goose/Goose.
    desktop = [p for p in found if "/usr/lib/goose/" in str(p) or p.name == "Goose"]
    clis = [p for p in found if p not in desktop]
    if desktop:
        info(f"desktop app installed ({desktop[0]}) — keep it on a similar version as the CLI")
    if len(clis) > 1:
        warn(
            f"{len(clis)} goose CLI binaries: " + ", ".join(str(p) for p in clis),
            "the first one in PATH wins — remove the others to avoid version confusion",
        )


# ── Ollama ────────────────────────────────────────────────────────────────────
def check_ollama():
    section("Ollama")
    try:
        version = http_json("/api/version").get("version", "?")
        ok(f"Ollama {version} reachable at {OLLAMA_URL}")
    except Exception:
        fail(f"Ollama not reachable at {OLLAMA_URL}", "sudo systemctl start ollama   (macOS: start the Ollama app)")
        return False

    try:
        names = [m.get("name", "") for m in http_json("/api/tags").get("models", [])]
    except Exception as e:
        fail(f"could not list models: {e}")
        return False

    def installed(model):
        return (model if ":" in model else f"{model}:latest") in names

    if installed(EMBED_MODEL):
        ok(f"embedding model {EMBED_MODEL} installed")
    else:
        fail(f"embedding model {EMBED_MODEL} not installed", f"ollama pull {EMBED_MODEL}")

    if installed(MODEL):
        ok(f"model {MODEL} installed")
        return True
    fail(f"model {MODEL} not installed", f"ollama pull {MODEL}")
    return False


# ── Python environment ────────────────────────────────────────────────────────
def check_python():
    section("Python")
    if sys.version_info < (3, 10):
        fail(f"Python {sys.version.split()[0]} — 3.10 or newer required")
    else:
        ok(f"Python {sys.version.split()[0]}")

    in_venv = sys.prefix != sys.base_prefix
    try:
        import chromadb  # noqa: F401
        ok(f"chromadb {chromadb.__version__}" + ("" if in_venv else " (not in a venv)"))
    except ImportError:
        if in_venv:
            fail("chromadb not installed in this venv", "pip install -r requirements.txt")
        else:
            fail("chromadb not found — is the venv active?",
                 "python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt")
        return

    try:
        import chainlit  # noqa: F401
        ok(f"chainlit {chainlit.__version__}")
    except ImportError:
        fail("chainlit not installed (chat UI, step 3)", "pip install -r requirements.txt")


# ── Java toolchain (only needed for exercise 1) ───────────────────────────────
def check_java():
    section("Java & Maven (exercise 1)")
    hint = "only needed for exercise 1 — the demo projects target Java 23"
    try:
        out = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=15)
        text = out.stderr + out.stdout
        m = re.search(r'version "(\d+)', text)
        major = int(m.group(1)) if m else 0
        if major >= 23:
            ok(f"Java {major}")
        else:
            warn(f"Java {major or '?'} — JDK 23 or newer required", hint)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        warn("java not found", hint)
    if shutil.which("mvn"):
        ok("Maven installed")
    else:
        warn("mvn not found", hint)


def check_model_runtime():
    section(f"Model runtime ({MODEL})")
    print("  … loading the model, this can take a moment")
    try:
        # A tiny request loads the model; keep it in memory briefly so /api/ps reports it.
        http_json(
            "/api/generate",
            {"model": MODEL, "prompt": "Say OK.", "stream": False, "think": False,
             "keep_alive": "2m", "options": {"num_predict": 5}},
            timeout=300,
        )
    except urllib.error.HTTPError as e:
        # Older Ollama versions reject the "think" field — retry without it.
        if e.code == 400:
            http_json(
                "/api/generate",
                {"model": MODEL, "prompt": "Say OK.", "stream": False,
                 "keep_alive": "2m", "options": {"num_predict": 5}},
                timeout=300,
            )
        else:
            fail(f"model failed to run: HTTP {e.code}")
            return
    except Exception as e:
        fail(f"model failed to run: {e}")
        return

    running = [m for m in http_json("/api/ps").get("models", [])
               if m.get("name") == MODEL or m.get("model") == MODEL]
    if not running:
        warn("model ran but is not listed in /api/ps — cannot check GPU and context")
        return
    m = running[0]

    size, vram = m.get("size", 0), m.get("size_vram", 0)
    gpu_pct = round(100 * vram / size) if size else 0
    if gpu_pct >= 99:
        ok("runs 100% on GPU")
    elif gpu_pct > 0:
        warn(f"runs {gpu_pct}% on GPU, rest on CPU", "works; a smaller model may be faster")
    else:
        warn("runs on CPU only — works, but slowly",
             "integrated GPU? try OLLAMA_IGPU_ENABLE=1 (section 1.2) or the fallback model qwen3:4b")

    ctx = m.get("context_length")
    if ctx is None:
        warn("Ollama does not report the context length — check OLLAMA_CONTEXT_LENGTH manually")
    elif ctx >= MIN_CONTEXT:
        ok(f"context length {ctx}")
    else:
        fail(f"context length only {ctx} (goose needs ≥ {MIN_CONTEXT})",
             "set OLLAMA_CONTEXT_LENGTH (section 1.2)")
    return ctx


# ── goose config ──────────────────────────────────────────────────────────────
def read_top_level(text, key):
    m = re.search(rf"^{key}:\s*['\"]?([^'\"\n#]+?)['\"]?\s*(#.*)?$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def read_provider_model(text, provider):
    """Newer goose versions keep a model per provider:

        providers:
          ollama:
            model: qwen3:8b
    """
    block = re.search(r"^providers:\s*\n((?:[ \t]+.*\n?|\s*\n)*)", text, re.MULTILINE)
    if not block or not provider:
        return None
    current = None
    for line in block.group(1).splitlines():
        m = re.match(r"^( +)([^\s:#][^:]*):\s*(.*?)\s*$", line)
        if not m:
            continue
        indent, key, value = len(m.group(1)), m.group(2).strip(), m.group(3)
        if not value:                       # provider name line, e.g. "  ollama:"
            current = key if indent <= 2 else current
        elif key == "model" and current == provider:
            return value.strip("'\"") or None
    return None


def check_goose_config(ollama_ctx):
    section(f"goose config ({GOOSE_CONFIG})")
    if not GOOSE_CONFIG.exists():
        fail("config not found", "run: goose configure")
        return
    text = GOOSE_CONFIG.read_text(encoding="utf-8", errors="ignore")

    # goose ≥ 1.5x: active_provider + providers.<name>.model; older: GOOSE_PROVIDER / GOOSE_MODEL
    provider = read_top_level(text, "active_provider") or read_top_level(text, "GOOSE_PROVIDER")
    if provider == "ollama":
        ok("provider: ollama — the agent runs locally")
    else:
        fail(f"provider: {provider or 'not set'} — code shared with goose may leave this machine",
             "goose configure → Configure Providers → Ollama")

    model = read_provider_model(text, provider) or read_top_level(text, "GOOSE_MODEL")
    if model == MODEL:
        ok(f"model: {model}")
    else:
        warn(f"model: {model or 'not set'} (workshop default: {MODEL})")

    # Read by the goose CLI and the desktop app. An environment variable of the same name overrides it.
    target = ollama_ctx if (ollama_ctx or 0) >= MIN_CONTEXT else 32768
    limit = read_top_level(text, "GOOSE_CONTEXT_LIMIT")
    env_limit = os.environ.get("GOOSE_CONTEXT_LIMIT")
    if env_limit:
        info(f"environment variable GOOSE_CONTEXT_LIMIT={env_limit} overrides the config for goose "
             "started from this terminal")
    if not limit:
        warn(f"GOOSE_CONTEXT_LIMIT not set — goose assumes 128k, Ollama serves {target}; "
             "long sessions lose their start silently",
             f"printf '\\nGOOSE_CONTEXT_LIMIT: {target}\\n' >> {GOOSE_CONFIG}")
    elif ollama_ctx and limit.isdigit() and int(limit) > ollama_ctx:
        warn(f"GOOSE_CONTEXT_LIMIT {limit} is larger than Ollama's context {ollama_ctx}",
             "use the same value in both places")
    else:
        ok(f"GOOSE_CONTEXT_LIMIT: {limit} (the chat shows …/{round(int(limit) / 1000)}k after the first message)"
           if limit.isdigit() else f"GOOSE_CONTEXT_LIMIT: {limit}")


def main():
    print("Local Code RAG Workshop — setup check")
    check_goose()
    ctx = None
    if check_ollama():
        ctx = check_model_runtime()
    check_goose_config(ctx)
    check_python()
    check_java()

    print(f"\n{results['ok']} ok · {results['warn']} warnings · {results['fail']} failed")
    if results["fail"]:
        print("Fix the ❌ items before the workshop — see docs/01-setup-goose-ollama.md and docs/02-index-a-codebase.md")
        sys.exit(1)
    print("Ready for the workshop 🎉" if not results["warn"] else "Ready — warnings are optional improvements.")


if __name__ == "__main__":
    main()
