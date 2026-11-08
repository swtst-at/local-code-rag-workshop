#!/usr/bin/env python3
"""
Retrieval eval — does the search find the right file? No LLM involved, fully deterministic.

    python3 eval_retrieval.py                                  # golden set of the indexed repo
    python3 eval_retrieval.py --set eval/golden_java.yaml
    python3 eval_retrieval.py -v                               # show what was found for misses

Compare setups by changing ONE thing and running again:

    EMBED_MODEL=qwen3-embedding python3 eval_retrieval.py      # another embedding model
    CHUNKER=generic python3 eval_retrieval.py                  # the generic chunker

Metrics
    Recall@k  share of questions whose expected file is among the first k results
    MRR       mean reciprocal rank: 1/rank of the first hit (rank 1 → 1.0, rank 2 → 0.5, miss → 0)
"""

import argparse
import sys
from pathlib import Path

from rag import golden
from rag.config import EMBED_MODEL, collection_name
from rag.ollama import OllamaError
from rag.search import IndexMissing, list_repos, search

DIM, RESET, BOLD, RED, GREEN = "\033[2m", "\033[0m", "\033[1m", "\033[31m", "\033[32m"
CUTOFFS = (1, 3, 5)


def pick_set(path: Path | None) -> Path:
    if path:
        return path
    repos = list_repos()
    if len(repos) != 1:
        sys.exit(f"❌ Index holds {len(repos) or 'no'} repositories ({', '.join(repos) or '—'}) — "
                 "pass --set eval/golden_<name>.yaml")
    p = golden.default_set_for(repos[0])
    if not p.exists():
        sys.exit(f"❌ No golden set for {repos[0]} — expected {p}")
    return p


def main():
    ap = argparse.ArgumentParser(description="Measure retrieval quality against a golden question set.")
    ap.add_argument("--set", type=Path, help="golden set (default: the one for the indexed repo)")
    ap.add_argument("-k", type=int, default=5, help="results per question (default 5)")
    ap.add_argument("--only", help="comma-separated question ids, e.g. K01,K12")
    ap.add_argument("-v", "--verbose", action="store_true", help="show the retrieved files for misses")
    args = ap.parse_args()

    try:
        gs = golden.load(pick_set(args.set), args.only.split(",") if args.only else None)
    except (ValueError, OSError) as e:
        sys.exit(f"❌ {e}")

    positives = [q for q in gs.questions if not q.negative]
    negatives = [q for q in gs.questions if q.negative]
    k = max(args.k, max(CUTOFFS))

    print(f"{BOLD}Retrieval eval{RESET} · {gs.path.name} · {EMBED_MODEL} · {collection_name()} · "
          f"repo {gs.repo} · top {k}\n")

    ranks = {}
    for q in positives:
        try:
            hits = search(q.question, k=k, repo=gs.repo)
        except (IndexMissing, OllamaError) as e:
            sys.exit(f"❌ {e}")
        rank = next((i for i, h in enumerate(hits, 1) if q.matches(h.path)), None)
        ranks[q.id] = rank
        mark = f"{GREEN}{rank:>4}{RESET}" if rank else f"{RED}miss{RESET}"
        print(f"  {q.id:<4} {mark}  {q.question}")
        if args.verbose and rank != 1:
            want = ", ".join(q.expect)
            print(f"{DIM}             expected {want}")
            for i, h in enumerate(hits, 1):
                print(f"             {i}. {h.score:.3f} {h.location}")
            print(RESET, end="")

    if not positives:
        sys.exit("No positive questions in this selection.")

    n = len(positives)
    recall = {c: sum(1 for r in ranks.values() if r and r <= c) / n for c in CUTOFFS}
    mrr = sum(1 / r for r in ranks.values() if r) / n
    misses = [qid for qid, r in ranks.items() if not r]

    print(f"\n{BOLD}" + " · ".join(f"Recall@{c} {recall[c]:.2f}" for c in CUTOFFS) + f" · MRR {mrr:.2f}{RESET}")
    print(f"{n} questions" + (f" · missed: {', '.join(misses)}" if misses else "") +
          (f" · {len(negatives)} negative questions skipped — see eval_answers.py" if negatives else ""))


if __name__ == "__main__":
    main()
