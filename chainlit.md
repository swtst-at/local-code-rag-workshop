# Local Code RAG

Ask questions about the indexed code. Everything runs on this machine:

- **Search** — the question is embedded with `nomic-embed-text` and compared with all code chunks in ChromaDB
- **Answer** — the best chunks go to `qwen3:8b`, which answers only from them and cites them as `[1]`, `[2]`, …

Open **Search the code index** above an answer to see what was retrieved.
Use ⚙ next to the input to choose the repository, the number of chunks and thinking mode.
