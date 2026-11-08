"""Golden question sets — load and validate eval/golden_*.yaml."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import PROJECT_ROOT

EVAL_DIR = PROJECT_ROOT / "eval"


@dataclass
class Question:
    id: str
    question: str
    expect: list[str] = field(default_factory=list)
    mention: list[str] = field(default_factory=list)   # words a correct answer names

    @property
    def negative(self) -> bool:
        """No expected file: the answer is not in the code."""
        return not self.expect

    def matches(self, path: str) -> bool:
        """Exact file name, or a path suffix if the entry contains a '/'.
        Not a plain substring: 'DriverFactory.kt' must not match 'WebDriverFactory.kt'."""
        path = path.replace("\\", "/")
        name = path.rsplit("/", 1)[-1]
        return any(path.endswith("/" + e.lstrip("/")) if "/" in e else name == e for e in self.expect)

    def answer_terms(self) -> list[str]:
        """What a correct answer should name: `mention`, else the expected file names and class names."""
        if self.mention:
            return self.mention
        terms = []
        for e in self.expect:
            name = e.rsplit("/", 1)[-1]
            terms.append(name)
            stem = name.rsplit(".", 1)[0]
            if any(c.isupper() for c in stem):        # a class name like WikipediaSteps
                terms.append(stem)
        return terms


@dataclass
class GoldenSet:
    path: Path
    repo: str
    questions: list[Question]


def default_set_for(repo: str) -> Path:
    short = repo.removeprefix("generated_")
    return EVAL_DIR / f"golden_{short}.yaml"


def load(path: Path, only: list[str] | None = None) -> GoldenSet:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "questions" not in data:
        raise ValueError(f"{path}: expected a mapping with 'repo' and 'questions'")
    questions = []
    for i, q in enumerate(data["questions"], 1):
        if "id" not in q or "question" not in q:
            raise ValueError(f"{path}: question #{i} needs 'id' and 'question'")
        questions.append(Question(id=str(q["id"]), question=q["question"],
                                  expect=list(q.get("expect") or []), mention=list(q.get("mention") or [])))
    if only:
        wanted = {o.strip() for o in only}
        questions = [q for q in questions if q.id in wanted]
        missing = wanted - {q.id for q in questions}
        if missing:
            raise ValueError(f"unknown question id(s): {', '.join(sorted(missing))}")
    return GoldenSet(path=path, repo=data.get("repo"), questions=questions)
