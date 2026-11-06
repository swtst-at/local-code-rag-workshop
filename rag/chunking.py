"""
Chunking — how source files are cut into pieces before they are embedded.

This is where most RAG quality is won or lost:

* too big    → one chunk mixes many topics, its embedding gets "blurry"
* too small  → a chunk loses the context needed to understand it
* wrong cuts → a function is split in half, retrieval finds only one part

Strategy here: cut at *meaningful boundaries* (declarations, Cucumber steps,
scenarios), then merge neighbouring pieces up to MAX_CHUNK_CHARS.
Every chunk gets a short header (file, class) so it still makes sense on its own.

Languages:
    kotlin, java   structure-aware (declarations, Cucumber steps, annotations)
    gherkin        one chunk per scenario
    generic        any other text file: cut at blank lines — works for every language, but blind
                   to structure. Compare it with the others: CHUNKER=generic

Try it:  python3 index.py --show-chunks path/to/File.kt
"""

import re
from dataclasses import dataclass, field

from .config import MAX_CHUNK_CHARS, OVERLAP_LINES, FORCE_GENERIC


@dataclass
class Chunk:
    text: str                 # what gets embedded and shown to the LLM (header + code)
    path: str                 # repo-relative path
    language: str
    start_line: int           # 1-based, inclusive
    end_line: int
    symbol: str = ""          # e.g. "WikipediaSteps", "Scenario: WIK-01 [wikipedia]"
    meta: dict = field(default_factory=dict)


@dataclass
class _Segment:
    start: int                # 0-based line index, inclusive
    end: int                  # exclusive
    symbol: str


# ── Cucumber step definitions (Kotlin and Java) ───────────────────────────────

# Lambda style (cucumber-java8):   Given("the start page is loaded") { ... }
#                                  Given("the start page is loaded", () -> { ... });
_STEP_LAMBDA = re.compile(r'^\s*(Given|When|Then|And|But)\s*\(\s*"(.*?)"')
# Annotation style (cucumber-java): @Given("the start page is loaded")  above a method
_STEP_ANNOTATION = re.compile(r'^\s*@(Given|When|Then|And|But)\s*\(\s*"(.*?)"')
# Hooks in lambda style:           Before { ... }   /   Before(() -> { ... });
_HOOK_LAMBDA = re.compile(r"^\s*(Before|After|BeforeStep|AfterStep|BeforeAll|AfterAll)\b\s*[({]")


# ── Kotlin ────────────────────────────────────────────────────────────────────

_KT_MODIFIERS = (
    r"(?:(?:public|private|protected|internal|open|abstract|sealed|data|enum|inner|"
    r"override|suspend|inline|operator|infix|tailrec|const|lateinit|companion|value|annotation)\s+)*"
)
_KT_DECLARATION = re.compile(
    rf"^\s*{_KT_MODIFIERS}(class|interface|object|fun|typealias)\b\s*(?:<[^>]*>\s*)?([\w.]*)"
)
_KT_TYPE = re.compile(rf"^{_KT_MODIFIERS}(class|interface|object)\s+(\w+)")   # top level only


def _kotlin_declaration(line: str) -> str | None:
    if m := _KT_DECLARATION.match(line):
        return f"{m.group(1)} {m.group(2)}".strip()
    return None


# ── Java ──────────────────────────────────────────────────────────────────────

_JAVA_MODIFIERS = (
    r"(?:(?:public|protected|private|static|final|abstract|sealed|non-sealed|strictfp|"
    r"synchronized|native|default|transient|volatile)\s+)*"
)
_JAVA_TYPE = re.compile(rf"^\s*{_JAVA_MODIFIERS}(class|interface|enum|record|@interface)\s+(\w+)")
# Methods and constructors: [modifiers] [<T>] [ReturnType] name(   — and no ';' (that would be a call)
_JAVA_METHOD = re.compile(
    rf"^\s*({_JAVA_MODIFIERS})(?:<[^>]+>\s+)?(?:([\w.]+(?:<.*?>)?(?:\[\])*)\s+)?(\w+)\s*\([^;]*$"
)
_JAVA_NOT_A_NAME = {"if", "for", "while", "switch", "catch", "return", "new", "else", "throw",
                    "try", "synchronized", "do", "super", "this"}


def _java_declaration(line: str) -> str | None:
    if m := _JAVA_TYPE.match(line):
        return f"{m.group(1)} {m.group(2)}"
    m = _JAVA_METHOD.match(line)
    if not m or "=" in line.split("(")[0]:                 # "Foo x = bar(" is an assignment
        return None
    modifiers, return_type, name = m.group(1).strip(), m.group(2), m.group(3)
    if name in _JAVA_NOT_A_NAME or return_type in _JAVA_NOT_A_NAME:
        return None
    if not modifiers and not return_type:                  # plain call like "assertThat(x)"
        return None
    return f"method {name}"


# ── Structure-aware chunker for Kotlin and Java ───────────────────────────────

_LANGUAGES = {
    #           declaration finder,  type finder (for the "Class:" header)
    "kotlin": (_kotlin_declaration, _KT_TYPE),
    "java": (_java_declaration, _JAVA_TYPE),
}


def _include_leading_comments(lines: list[str], idx: int, floor: int) -> int:
    """Move a boundary up so doc comments and annotations stay with their declaration."""
    while idx - 1 >= floor:
        prev = lines[idx - 1].strip()
        if prev.startswith(("@", "/**", "/*", "*", "*/", "//")):
            idx -= 1
        else:
            break
    return idx


def chunk_source(text: str, path: str, language: str) -> list[Chunk]:
    find_declaration, type_re = _LANGUAGES[language]
    lines = text.splitlines()

    # The file header (package + imports) is noise for retrieval — skip it, remember the package.
    package = ""
    body_start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("package "):
            package = s.removeprefix("package ").rstrip(";").strip()
            body_start = i + 1
        elif s.startswith("import ") or s == "":
            body_start = i + 1
        else:
            break

    # Find boundaries — places where a new logical unit starts
    starts = []
    step_annotation_open = False      # an @Given(...) was seen; the method below belongs to it
    for i in range(body_start, len(lines)):
        line = lines[i]
        if m := _STEP_LAMBDA.match(line):
            starts.append((i, f'{m.group(1)}("{m.group(2)}")'))
        elif m := _STEP_ANNOTATION.match(line):
            starts.append((_include_leading_comments(lines, i, body_start), f'{m.group(1)}("{m.group(2)}")'))
            step_annotation_open = True
        elif m := _HOOK_LAMBDA.match(line):
            starts.append((i, m.group(1)))
        elif symbol := find_declaration(line):
            if step_annotation_open:          # method of an annotated step — already covered
                step_annotation_open = False
                continue
            starts.append((_include_leading_comments(lines, i, body_start), symbol))
        elif line.strip() and not line.strip().startswith(("@", "//", "/*", "*")):
            step_annotation_open = False
    if not starts or starts[0][0] > body_start:
        starts.insert(0, (body_start, ""))

    segments = []
    for n, (start, symbol) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        if start < end:
            segments.append(_Segment(start, end, symbol))

    def enclosing_type(line_idx: int) -> str:
        for i in range(min(line_idx, len(lines) - 1), -1, -1):
            if m := type_re.match(lines[i]):
                return m.group(2)
        return ""

    def header(seg_start: int) -> str:
        parts = [f"// File: {path}"]
        if package:
            parts.append(f"// Package: {package}")
        if cls := enclosing_type(seg_start):
            parts.append(f"// Class: {cls}")
        return "\n".join(parts)

    return _merge(segments, lines, path, language, header)


# Kept for readability in the workshop: "the Kotlin chunker"
def chunk_kotlin(text: str, path: str) -> list[Chunk]:
    return chunk_source(text, path, "kotlin")


def chunk_java(text: str, path: str) -> list[Chunk]:
    return chunk_source(text, path, "java")


# ── Gherkin (.feature) ────────────────────────────────────────────────────────

_SCENARIO = re.compile(r"^\s*(Scenario Outline|Scenario Template|Scenario|Example|Background|Rule)\s*:\s*(.*)")
_FEATURE = re.compile(r"^\s*Feature\s*:\s*(.*)")


def chunk_gherkin(text: str, path: str) -> list[Chunk]:
    """One chunk per scenario (incl. its tags and Examples), each prefixed with the Feature line."""
    lines = text.splitlines()
    feature = next((m.group(0).strip() for l in lines if (m := _FEATURE.match(l))), "")

    starts = []
    for i, line in enumerate(lines):
        if m := _SCENARIO.match(line):
            start = i
            while start > 0 and lines[start - 1].strip().startswith(("@", "#")):
                start -= 1                       # keep tags with their scenario
            starts.append((start, f"{m.group(1)}: {m.group(2).strip()}"))

    if not starts:                               # feature without scenarios
        starts = [(0, feature)]

    segments = [
        _Segment(start, starts[n + 1][0] if n + 1 < len(starts) else len(lines), symbol)
        for n, (start, symbol) in enumerate(starts)
    ]
    return _merge(segments, lines, path, "gherkin",
                  lambda _: f"# File: {path}\n# {feature}", merge=False)


# ── Generic fallback ──────────────────────────────────────────────────────────

def chunk_generic(text: str, path: str, language: str = "generic") -> list[Chunk]:
    """Cut at blank lines, merge up to MAX_CHUNK_CHARS. Knows nothing about the language."""
    lines = text.splitlines()
    starts = [0] + [i + 1 for i, l in enumerate(lines[:-1]) if not l.strip() and lines[i + 1].strip()]
    segments = [
        _Segment(s, starts[n + 1] if n + 1 < len(starts) else len(lines), "")
        for n, s in enumerate(starts)
    ]
    return _merge(segments, lines, path, language, lambda _: f"File: {path}")


# ── Shared ────────────────────────────────────────────────────────────────────

def _merge(segments, lines, path, language, header_fn, merge=True) -> list[Chunk]:
    """Greedily merge neighbouring segments up to MAX_CHUNK_CHARS; split oversized ones."""
    groups: list[list[_Segment]] = []
    size = 0
    for seg in segments:
        seg_size = sum(len(l) + 1 for l in lines[seg.start:seg.end])
        if merge and groups and size + seg_size <= MAX_CHUNK_CHARS:
            groups[-1].append(seg)
            size += seg_size
        else:
            groups.append([seg])
            size = seg_size

    chunks = []
    for group in groups:
        start, end = group[0].start, group[-1].end
        symbols = [s.symbol for s in group if s.symbol]
        for a, b in _split_lines(lines, start, end):
            code = "\n".join(lines[a:b]).strip("\n")
            if not code.strip():
                continue
            chunks.append(Chunk(
                text=f"{header_fn(a)}\n\n{code}",
                path=path,
                language=language,
                start_line=a + 1,
                end_line=b,
                symbol=", ".join(symbols[:3]) + (" …" if len(symbols) > 3 else ""),
            ))
    return chunks


def _split_lines(lines, start, end):
    """Cut a range that is still too large into line-based windows with a small overlap."""
    a = start
    while a < end:
        b, size = a, 0
        while b < end and (size == 0 or size + len(lines[b]) + 1 <= MAX_CHUNK_CHARS):
            size += len(lines[b]) + 1
            b += 1
        yield a, b
        if b >= end:
            break
        a = max(b - OVERLAP_LINES, a + 1)


def chunk_file(text: str, path: str, language: str) -> list[Chunk]:
    if FORCE_GENERIC:
        return chunk_generic(text, path, language)
    if language in _LANGUAGES:
        return chunk_source(text, path, language)
    if language == "gherkin":
        return chunk_gherkin(text, path)
    return chunk_generic(text, path, language)
