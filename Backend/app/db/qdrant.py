import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter

from app.config import settings

client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
COLLECTION = settings.qdrant_collection


def ensure_collection(name: str = COLLECTION, dim: int = settings.embed_dim) -> None:
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def reset_collection(name: str = COLLECTION, dim: int = settings.embed_dim) -> None:
    """Drop and recreate (dev reset)."""
    if client.collection_exists(name):
        client.delete_collection(name)
    ensure_collection(name, dim)


def upsert_chunks(chunks: list[dict]) -> int:
    """Each chunk: {vector, text, source_id, source_title, node_ids, chunk_idx}.
    Point id is deterministic, so re-ingesting a doc overwrites instead of duplicating."""
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{c['source_id']}:{c['chunk_idx']}")),
            vector=c["vector"],
            payload={k: c[k] for k in ("text", "source_id", "source_title", "node_ids", "chunk_idx")},
        )
        for c in chunks
    ]
    if points:
        client.upsert(collection_name=COLLECTION, points=points)
    return len(points)


def search(vector: list[float], k: int = settings.top_k_chunks, query_filter: Filter | None = None) -> list[dict]:
    res = client.query_points(
        collection_name=COLLECTION, query=vector, limit=k,
        query_filter=query_filter, with_payload=True,
    )
    return [{"score": p.score, **(p.payload or {})} for p in res.points]


def ping() -> bool:
    try:
        client.get_collections()
        return True
    except Exception:
        return False