#!/usr/bin/env python3
"""
Print the exact values to register the MCP server as a goose extension — with the absolute
paths of *this* checkout, so nothing has to be typed by hand.

    python3 scripts/goose_extension.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server.py"

# goose starts the server itself, without your activated venv — so we point at the venv's python.
venv_python = ROOT / ".venv" / "bin" / "python"
if not venv_python.exists():
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"      # Windows
python = venv_python if venv_python.exists() else Path(sys.executable)

if not venv_python.exists():
    print("⚠️  No .venv found in this checkout — using the current Python instead:")
    print(f"   {python}")
    print("   Create the venv first (docs/02-index-a-codebase.md, section 2.1).\n")

command = f"{python} {SERVER}"

print(f"""\
goose Desktop  →  Extensions  →  Add custom extension
───────────────────────────────────────────────────────
  Extension Name   local-code-rag
  Type             STDIO
  Description      Local semantic search over the indexed code
  Command          {command}
  Timeout          300

goose CLI — one session with the extension
───────────────────────────────────────────────────────
  goose session --with-extension "{command}"

~/.config/goose/config.yaml — under "extensions:"
───────────────────────────────────────────────────────
  local-code-rag:
    enabled: true
    name: local-code-rag
    type: stdio
    cmd: {python}
    args:
    - {SERVER}
    envs: {{}}
    timeout: 300
    description: Local semantic search over the indexed code

Test the server on its own (opens the MCP Inspector in the browser, needs Node.js):
  npx @modelcontextprotocol/inspector {command}
""")
