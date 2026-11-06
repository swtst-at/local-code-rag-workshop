"""
Retrieval — find the chunks that are most similar to a question.

This is the "R" in RAG. If the right code is not among the hits,
no LLM can give a correct answer. Always check retrieval first.
"""

from dataclasses import dataclass

from .config import EMBED_MODEL, TOP_K
from .ollama import embed_query


class IndexMissing(RuntimeError):
    pass


@dataclass
class Hit:
    text: str
    repo: str
    path: str
    start_line: int
    end_line: int
    symbol: str
    language: str
    score: float          # cosine similarity: 1.0 = identical direction, 0 = unrelated

    @property
    def location(self) -> str:
        return f"{self.path}:{self.start_line}-{self.end_line}"

    @property
    def short_location(self) -> str:
        return f"{self.path.rsplit('/', 1)[-1]}:{self.start_line}-{self.end_line}"


def search(query: str, k: int = TOP_K, repo: str | None = None) -> list[Hit]:
    from .store import get_collection
    try:
        col = get_collection(create=False)
    except Exception as e:
        raise IndexMissing(
            f"No index for embedding model '{EMBED_MODEL}' — run: python3 index.py <repo>"
        ) from e
    if col.count() == 0:
        raise IndexMissing("The index is empty — run: python3 index.py <repo>")

    result = col.query(
        query_embeddings=[embed_query(query)],
        n_results=min(k, col.count()),
        where={"repo": repo} if repo else None,
        include=["documents", "metadatas", "distances"],
    )
    return [
        Hit(
            text=doc,
            repo=meta["repo"],
            path=meta["path"],
            start_line=meta["start_line"],
            end_line=meta["end_line"],
            symbol=meta.get("symbol", ""),
            language=meta.get("language", ""),
            score=round(1 - dist, 3),
        )
        for doc, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0])
    ]


def list_repos() -> list[str]:
    from .store import get_collection
    try:
        metas = get_collection(create=False).get(include=["metadatas"])["metadatas"]
    except Exception:
        return []
    return sorted({m["repo"] for m in metas})
