from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # LLM (Groq, OpenAI-compatible)
    llm_api_key: str
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_router_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = 0.2
    llm_timeout: int = 30
    llm_max_retries: int = 2

    # Embeddings
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384

    # FalkorDB
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: str = ""
    falkordb_graph: str = "rampup"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "rampup_chunks"

    # Retrieval
    top_k_chunks: int = 5
    graph_hops: int = 2
    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 50

    # App
    cors_origins: str = "http://localhost:5173"
    data_dir: str = "../data"

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        if p.is_absolute() and p.exists():
            return p
        if (BACKEND_DIR / p).exists():
            return (BACKEND_DIR / p).resolve()
        if (BACKEND_DIR.parent / p).exists():
            return (BACKEND_DIR.parent / p).resolve()
        return (BACKEND_DIR / p).resolve()


settings = Settings()