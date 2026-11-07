#!/usr/bin/env python3
"""
Ask a question — retrieval + answer from the local LLM, streamed to the terminal.

    python3 ask.py "How are page objects created?"
    python3 ask.py "How are page objects created?" --repo generated_java
    python3 ask.py "How are page objects created?" --think        # let qwen3 reason first (slower)
    python3 ask.py "How are page objects created?" --show-prompt  # see exactly what the LLM gets
    python3 ask.py "What does the login step do?" --prompt basic  # compare system prompts
"""

import argparse
import sys

from rag.answer import PROMPTS, answer_stream, build_messages
from rag.config import LLM_MODEL, LLM_THINK, PROMPT, TOP_K
from rag.ollama import OllamaError
from rag.search import IndexMissing, search

DIM, RESET, BOLD = "\033[2m", "\033[0m", "\033[1m"


def main():
    p = argparse.ArgumentParser(description="Ask a question about the indexed code (100% local).")
    p.add_argument("question")
    p.add_argument("-k", type=int, default=TOP_K, help=f"number of chunks given to the LLM (default {TOP_K})")
    p.add_argument("--repo", help="only use this repository (folder name)")
    p.add_argument("--model", default=LLM_MODEL, help=f"Ollama model (default {LLM_MODEL})")
    p.add_argument("--think", action="store_true", default=LLM_THINK, help="enable the reasoning phase")
    p.add_argument("--prompt", default=PROMPT, choices=list(PROMPTS),
                   help=f"system prompt variant (default {PROMPT}) — compare with 'basic'")
    p.add_argument("--show-prompt", action="store_true", help="print the full prompt before answering")
    args = p.parse_args()
    if args.prompt not in PROMPTS:          # e.g. a typo in the PROMPT environment variable
        sys.exit(f"❌ Unknown prompt '{args.prompt}' — choose one of: {', '.join(PROMPTS)}")

    try:
        hits = search(args.question, k=args.k, repo=args.repo)
    except (IndexMissing, OllamaError) as e:
        sys.exit(f"❌ {e}")

    if args.show_prompt:
        for m in build_messages(args.question, hits, args.prompt):
            print(f"{DIM}── {m['role']} ──\n{m['content']}{RESET}\n")

    print(f"{BOLD}🔒 {args.model}{' (thinking)' if args.think else ''} · {len(hits)} chunks · "
          f"prompt '{args.prompt}'{RESET}\n")

    stats, thinking_started = {}, False
    try:
        for kind, value in answer_stream(args.question, hits, model=args.model, think=args.think,
                                         prompt=args.prompt):
            if kind == "thinking":
                if not thinking_started:
                    print(f"{DIM}💭 ", end="")
                    thinking_started = True
                print(f"{DIM}{value}{RESET}", end="", flush=True)
            elif kind == "content":
                if thinking_started:
                    print(f"{RESET}\n")
                    thinking_started = False
                print(value, end="", flush=True)
            elif kind == "done":
                stats = value
    except OllamaError as e:
        sys.exit(f"\n❌ {e}")
    except KeyboardInterrupt:
        sys.exit(f"{RESET}\n⏹  interrupted")

    print(f"\n\n{BOLD}Sources{RESET}")
    for i, h in enumerate(hits, 1):
        print(f"  [{i}] {h.repo}/{h.location}  {DIM}{h.symbol} · score {h.score:.3f}{RESET}")

    if stats:
        print(f"\n{DIM}⏱ {stats['seconds']:.1f}s · prompt {stats['prompt_tokens']} tokens · "
              f"answer {stats['answer_tokens']} tokens at {stats['tokens_per_second']:.1f} tok/s{RESET}")


if __name__ == "__main__":
    main()
