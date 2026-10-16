from sentence_transformers import SentenceTransformer

from app.config import settings

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embed_model)
    return _model


def warmup() -> None:
    """Call at startup so the first request isn't slow."""
    _get_model()


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vecs = _get_model().encode(texts, batch_size=32, normalize_embeddings=True)
    return vecs.tolist()


def embed_one(text: str) -> list[float]:
    return embed([text])[0]