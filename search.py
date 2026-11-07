#!/usr/bin/env python3
"""
Retrieval only — show which chunks the index returns for a question. No LLM involved.

    python3 search.py "Where is the WebDriver created?"
    python3 search.py "Where is the WebDriver created?" --repo generated_java -k 8
    python3 search.py "searchbar visible" --code          # also print the code

Check retrieval *before* blaming the LLM: if the right code is not here, no model can answer well.
"""

import argparse
import sys

from rag.config import EMBED_MODEL, TOP_K
from rag.ollama import OllamaError
from rag.search import IndexMissing, search


def main():
    p = argparse.ArgumentParser(description="Semantic search over the local code index (no LLM).")
    p.add_argument("question")
    p.add_argument("-k", type=int, default=TOP_K, help=f"number of results (default {TOP_K})")
    p.add_argument("--repo", help="only search this repository (folder name)")
    p.add_argument("--code", action="store_true", help="print the code of each hit")
    args = p.parse_args()

    try:
        hits = search(args.question, k=args.k, repo=args.repo)
    except (IndexMissing, OllamaError) as e:
        sys.exit(f"❌ {e}")

    print(f"🔍 {args.question}   [{EMBED_MODEL}]\n")
    if not hits:
        print("No results.")
        return
    width = max(len(f"{h.repo}/{h.location}") for h in hits)
    for i, h in enumerate(hits, 1):
        bar = "█" * round(h.score * 20)
        print(f"{i:>2}. {h.score:.3f} {bar:<20} {h.repo}/{h.location:<{width - len(h.repo) - 1}}  {h.symbol}")
        if args.code:
            print("\n" + "\n".join("      " + l for l in h.text.splitlines()) + "\n")


if __name__ == "__main__":
    main()
