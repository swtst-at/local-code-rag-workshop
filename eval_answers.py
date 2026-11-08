#!/usr/bin/env python3
"""
Answer eval — ask every golden question several times and count how often the answer passes.

    python3 eval_answers.py                          # 3 runs per question — takes a few minutes
    python3 eval_answers.py --runs 5 --only K01,N01  # a few questions, more runs
    python3 eval_answers.py --prompt basic           # compare system prompts
    python3 eval_answers.py -v                       # print every answer

Retrieval runs ONCE per question (it is deterministic); only the generation is repeated.
So every difference between the runs comes from the LLM.

Checks — simple and visible on purpose, like any test oracle:
    every answer       each file name it mentions (*.kt, *.java, *.feature) exists in the index
    positive question  the answer names the expected file or class (golden set: `mention`, else `expect`)
                       and does not claim that nothing was found
    negative question  the answer says it could not find it
Read failing answers with -v before you trust the numbers.
"""

import argparse
import re
import sys
import time
from pathlib import Path

from eval_retrieval import pick_set
from rag import golden
from rag.answer import PROMPTS, answer_stream
from rag.config import LLM_MODEL, LLM_THINK, PROMPT, TOP_K
from rag.ollama import OllamaError
from rag.search import IndexMissing, list_files, search

DIM, RESET, BOLD, RED, GREEN = "\033[2m", "\033[0m", "\033[1m", "\033[31m", "\033[32m"

NOT_FOUND = re.compile(
    r"(could not|couldn['’]t|cannot|can['’]t|did not|didn['’]t|unable to) (find|locate|see|identify)"
    r"|not (be )?found"
    r"|(does|do) not (contain|include|mention|show|define|provide|describe|cover)"
    r"|(doesn['’]t|don['’]t) (contain|include|mention|show|define|provide|describe|cover)"
    r"|no (information|details|mention|indication)"
    r"|there is no |there are no |no (such|login|password|rest)"
    r"|not (present|available|part of) (in )?the (searched )?code",
    re.IGNORECASE,
)


FILE_NAME = re.compile(r"\b[\w-]+\.(?:kt|kts|java|feature)\b")


def check(q: golden.Question, answer: str, known_files: set[str]) -> tuple[bool, str]:
    # Hallucination check: every file name the answer mentions must exist in the index.
    invented = sorted({f for f in FILE_NAME.findall(answer) if known_files and f not in known_files})
    if invented:
        return False, f"invents {', '.join(invented)}"
    says_not_found = bool(NOT_FOUND.search(answer))
    if q.negative:
        return (True, "says not found") if says_not_found else (False, "does not say it is missing")
    terms = q.answer_terms()
    # whole words only: "DriverFactory" must not match "WebDriverFactory"
    named = [t for t in terms if re.search(rf"(?<![\w.]){re.escape(t)}(?!\w)", answer, re.IGNORECASE)]
    if not named:
        return False, f"names none of: {', '.join(terms)}"
    if says_not_found:
        return False, f"names {named[0]} but also claims not found"
    return True, f"names {named[0]}"


def generate(question: str, hits, args) -> tuple[str, float]:
    parts, t0 = [], time.time()
    for kind, value in answer_stream(question, hits, model=args.model, think=args.think, prompt=args.prompt):
        if kind == "content":
            parts.append(value)
    return "".join(parts).strip(), time.time() - t0


def main():
    ap = argparse.ArgumentParser(description="Measure answer quality over several runs per question.")
    ap.add_argument("--set", type=Path, help="golden set (default: the one for the indexed repo)")
    ap.add_argument("--runs", type=int, default=3, help="answers per question (default 3)")
    ap.add_argument("--only", help="comma-separated question ids, e.g. K01,N01")
    ap.add_argument("-k", type=int, default=TOP_K, help=f"chunks given to the LLM (default {TOP_K})")
    ap.add_argument("--model", default=LLM_MODEL, help=f"Ollama model (default {LLM_MODEL})")
    ap.add_argument("--prompt", default=PROMPT, choices=list(PROMPTS), help=f"system prompt (default {PROMPT})")
    ap.add_argument("--think", action="store_true", default=LLM_THINK, help="enable the reasoning phase")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every answer")
    args = ap.parse_args()

    try:
        gs = golden.load(pick_set(args.set), args.only.split(",") if args.only else None)
    except (ValueError, OSError) as e:
        sys.exit(f"❌ {e}")

    total = len(gs.questions) * args.runs
    print(f"{BOLD}Answer eval{RESET} · {gs.path.name} · {args.model} · prompt {args.prompt}"
          f"{' · thinking' if args.think else ''} · {args.runs} runs × {len(gs.questions)} questions")
    print(f"{DIM}{total} answers — roughly {total * 10 // 60 + 1} min at ~10 s per answer on a laptop{RESET}\n")

    known_files = list_files(gs.repo)
    t_start = time.time()
    passed_total, stable = 0, 0
    failed_ids = []
    for q in gs.questions:
        try:
            hits = search(q.question, k=args.k, repo=gs.repo)
        except (IndexMissing, OllamaError) as e:
            sys.exit(f"❌ {e}")

        results = []
        print(f"  {q.id:<4} ", end="", flush=True)
        for _ in range(args.runs):
            try:
                answer, seconds = generate(q.question, hits, args)
            except OllamaError as e:
                sys.exit(f"\n❌ {e}")
            ok, reason = check(q, answer, known_files)
            results.append((ok, reason, answer, seconds))
            print(f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}", end="", flush=True)

        n_ok = sum(1 for r in results if r[0])
        passed_total += n_ok
        if n_ok in (0, args.runs):
            stable += 1
        if n_ok < args.runs:
            failed_ids.append(q.id)
        kind = "negative" if q.negative else "positive"
        print(f"  {n_ok}/{args.runs}  {q.question} {DIM}({kind}){RESET}")

        if args.verbose or n_ok < args.runs:
            for i, (ok, reason, answer, seconds) in enumerate(results, 1):
                if args.verbose or not ok:
                    short = " ".join(answer.split())
                    short = short if len(short) <= 220 else short[:217] + "…"
                    print(f"{DIM}         run {i}: {'pass' if ok else 'FAIL'} — {reason} · {seconds:.1f}s\n"
                          f"         “{short}”{RESET}")

    minutes, seconds = divmod(int(time.time() - t_start), 60)
    rate = passed_total / total if total else 0
    print(f"\n{BOLD}Pass rate {passed_total}/{total} ({rate:.0%}){RESET} · "
          f"same result in every run: {stable} of {len(gs.questions)} questions · {minutes} min {seconds} s")
    if failed_ids:
        print(f"Not always passing: {', '.join(failed_ids)}")


if __name__ == "__main__":
    main()
