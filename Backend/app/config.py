from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    llm_provider: str = "gemini"
    demo_mode: bool = False
    gemini_timeout_seconds: int = 30
    gemini_max_retries: int = 2

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: str = ""
    falkordb_graph: str = "onboardos"

    cors_origins: str = "http://localhost:5173"
    transcript_dir: Path = PROJECT_DIR / "data" / "transcripts"
    max_transcript_bytes: int = 2_000_000
    max_transcript_chars: int = 100_000
    transcript_chunk_chars: int = 12_000
    max_evidence_items: int = 12

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def resolve_transcript_directory(self):
        if not self.transcript_dir.is_absolute():
            self.transcript_dir = (BACKEND_DIR / self.transcript_dir).resolve()
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
