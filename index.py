#!/usr/bin/env python3
"""
Index a codebase into the local vector database.

    python3 index.py ../generated_kotlin              # index (only changed files)
    python3 index.py ../generated_kotlin --force      # rebuild this repo from scratch
    python3 index.py --remove generated_java          # take a repo out of the index
    python3 index.py --show-chunks path/to/File.kt    # see how a file is chunked (no Ollama needed)
    python3 index.py --stats                          # what is in the index?

Environment: EMBED_MODEL (default nomic-embed-text), OLLAMA_URL, RAG_DB_PATH, MAX_CHUNK_CHARS,
             EXTRA_FILE_TYPES (e.g. ".py,.ts"), CHUNKER=generic
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

from rag import config
from rag.chunking import chunk_file
from rag.ollama import OllamaError, embed_documents, require_model


def find_files(repo: Path) -> list[Path]:
    return sorted(
        f for f in repo.rglob("*")
        if f.is_file()
        and f.suffix in config.FILE_TYPES
        and not any(part in config.IGNORE_DIRS for part in f.relative_to(repo).parts)
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def show_chunks(file: Path) -> None:
    language = config.FILE_TYPES.get(file.suffix, "generic")    # unknown types: generic chunker
    chunks = chunk_file(file.read_text(encoding="utf-8", errors="ignore"), file.name, language)
    for i, c in enumerate(chunks, 1):
        print(f"\n━━━ chunk {i}/{len(chunks)} · lines {c.start_line}-{c.end_line} · "
              f"{len(c.text)} chars · {c.symbol or '—'}")
        print(c.text)
    print(f"\n{len(chunks)} chunks (MAX_CHUNK_CHARS={config.MAX_CHUNK_CHARS})")


def show_stats() -> None:
    from rag.store import get_collection
    try:
        col = get_collection(create=False)
    except Exception:
        sys.exit(f"No index for embedding model '{config.EMBED_MODEL}' yet — run: python3 index.py <repo>")
    metas = col.get(include=["metadatas"])["metadatas"]
    print(f"Collection   {col.name}  ({config.DB_PATH})")
    print(f"Chunks       {len(metas)}")
    for repo in sorted({m["repo"] for m in metas}):
        repo_metas = [m for m in metas if m["repo"] == repo]
        files = {m["path"] for m in repo_metas}
        print(f"\n  {repo}  ({repo_metas[0].get('repo_path', '')})")
        print(f"    {len(files)} files · {len(repo_metas)} chunks")
        for lang in sorted({m["language"] for m in repo_metas}):
            print(f"    {lang:<10} {sum(1 for m in repo_metas if m['language'] == lang)} chunks")


def remove(repo_name: str) -> None:
    from rag.store import get_collection
    try:
        col = get_collection(create=False)
    except Exception:
        sys.exit(f"No index for embedding model '{config.EMBED_MODEL}'")
    ids = col.get(where={"repo": repo_name}, include=[])["ids"]
    if not ids:
        repos = sorted({m["repo"] for m in col.get(include=["metadatas"])["metadatas"]})
        sys.exit(f"❌ '{repo_name}' is not in the index. Indexed: {', '.join(repos) or 'nothing'}")
    col.delete(ids=ids)
    print(f"🗑  removed {repo_name} ({len(ids)} chunks) from {col.name}")


def index(repo: Path, force: bool) -> None:
    from rag.store import get_collection

    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        sys.exit(f"❌ Not a directory: {repo}")

    try:
        require_model(config.EMBED_MODEL)
    except OllamaError as e:
        sys.exit(f"❌ {e}")

    print(f"🔒 Local indexing — embeddings via Ollama ({config.EMBED_MODEL}), nothing leaves this machine")
    print(f"📁 {repo}")

    files = find_files(repo)
    if not files:
        sys.exit(f"❌ No {', '.join(config.FILE_TYPES)} files found")

    # Several repositories can share one index. Every chunk carries its repo name,
    # and all bookkeeping below only looks at the chunks of *this* repo.
    repo_name = repo.name
    this_repo = {"repo": repo_name}

    col = get_collection()
    if force:
        existing = col.get(where=this_repo, include=[])["ids"]
        if existing:
            col.delete(ids=existing)

    # What is already indexed? path → content hash
    indexed = {m["path"]: m["hash"] for m in col.get(where=this_repo, include=["metadatas"])["metadatas"]}
    current = {str(f.relative_to(repo)): f for f in files}

    removed = sorted(set(indexed) - set(current))
    changed, unchanged = [], 0
    for rel, f in current.items():
        h = sha256(f)
        if indexed.get(rel) == h:
            unchanged += 1
        else:
            changed.append((rel, f, h))

    # Delete stale chunks: removed files, and the old version of changed files.
    for rel in removed + [rel for rel, _, _ in changed if rel in indexed]:
        col.delete(where={"$and": [this_repo, {"path": rel}]})

    chunks = []
    for rel, f, h in changed:
        for i, c in enumerate(chunk_file(f.read_text(encoding="utf-8", errors="ignore"),
                                         rel, config.FILE_TYPES[f.suffix])):
            c.meta = {"id": f"{repo_name}/{rel}::{i}", "hash": h}
            chunks.append(c)

    print(f"   {len(files)} files · {unchanged} unchanged · {len(changed)} new/changed · {len(removed)} removed")
    if not chunks:
        print("✅ Index is up to date")
        return

    t0 = time.time()
    batch = config.EMBED_BATCH_SIZE
    for i in range(0, len(chunks), batch):
        part = chunks[i : i + batch]
        print(f"   embedding {min(i + batch, len(chunks))}/{len(chunks)} chunks …", end="\r", flush=True)
        try:
            vectors = embed_documents([c.text for c in part])
        except OllamaError as e:
            sys.exit(f"\n❌ {e}")
        col.upsert(
            ids=[c.meta["id"] for c in part],
            documents=[c.text for c in part],
            embeddings=vectors,
            metadatas=[{
                "path": c.path, "hash": c.meta["hash"], "language": c.language,
                "start_line": c.start_line, "end_line": c.end_line,
                "symbol": c.symbol, "repo": repo_name, "repo_path": str(repo),
            } for c in part],
        )

    print(f"\n✅ {len(chunks)} chunks embedded in {time.time() - t0:.1f}s → {config.DB_PATH} "
          f"[{col.name}]")


def main():
    p = argparse.ArgumentParser(description="Index a codebase into the local vector database.")
    p.add_argument("repo", nargs="?", type=Path, help="path to the repository to index")
    p.add_argument("--force", action="store_true", help="drop this repo's part of the index and rebuild it")
    p.add_argument("--show-chunks", type=Path, metavar="FILE", help="print the chunks of one file and exit")
    p.add_argument("--stats", action="store_true", help="show what is in the index")
    p.add_argument("--remove", metavar="REPO", help="remove a repository (folder name) from the index")
    args = p.parse_args()

    if args.show_chunks:
        show_chunks(args.show_chunks)
    elif args.stats:
        show_stats()
    elif args.remove:
        remove(args.remove)
    elif args.repo:
        index(args.repo, args.force)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
