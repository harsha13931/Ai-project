"""Centralised configuration — every API key and setting in one place.

Set values via environment variables or a .env file.  The rest of the app
imports ``settings`` from here and never reads os.environ directly.
"""
import os
from pathlib import Path


class Settings:
    # ── LLM (Anthropic Claude) ─────────────────────────────────────────
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "")

    # ── Embeddings (HuggingFace — free, local, no API key) ─────────────
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")

    # ── RAG tuning ─────────────────────────────────────────────────────
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "900"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    RETRIEVAL_K: int = int(os.getenv("RETRIEVAL_K", "4"))
    SCORE_THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", "0.05"))

    # ── Persistence ────────────────────────────────────────────────────
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
    DB_PATH: Path = Path(os.getenv("DB_PATH", "")) or DATA_DIR / "docmind.db"
    FAISS_DIR: Path = Path(os.getenv("FAISS_DIR", "")) or DATA_DIR / "faiss_index"

    # ── Security ───────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    RATE_LIMIT: str = os.getenv("RATE_LIMIT", "30/minute")
    RATE_LIMIT_UPLOAD: str = os.getenv("RATE_LIMIT_UPLOAD", "10/minute")
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    DOC_RETENTION_HOURS: int = int(os.getenv("DOC_RETENTION_HOURS", "0"))

    # ── Convenience flags ──────────────────────────────────────────────
    @property
    def llm_enabled(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY and self.ANTHROPIC_MODEL)


settings = Settings()
