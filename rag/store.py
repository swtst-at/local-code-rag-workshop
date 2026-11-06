"""ChromaDB access — a local vector database stored in ./db (no server, no network)."""

import chromadb
from chromadb.config import Settings

from .config import DB_PATH, EMBED_MODEL, collection_name


def get_collection(embed_model: str = EMBED_MODEL, create: bool = True):
    client = chromadb.PersistentClient(
        path=str(DB_PATH),
        settings=Settings(anonymized_telemetry=False),   # keep it local — no telemetry pings
    )
    name = collection_name(embed_model)
    if create:
        return client.get_or_create_collection(
            name, metadata={"hnsw:space": "cosine", "embed_model": embed_model}
        )
    return client.get_collection(name)
