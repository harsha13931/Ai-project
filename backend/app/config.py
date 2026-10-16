"""Centralised configuration — every API key and setting in one place.

Set values via environment variables or a .env file.  The rest of the app
imports ``settings`` from here and never reads os.environ directly.
"""
import os


class Settings:
    # ── LLM (Anthropic Claude) ─────────────────────────────────────────
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "")

    # ── Embeddings (HuggingFace — free, local, no API key) ─────────────
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "all-MiniLM-L6-v2"
    )
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")

    # ── RAG tuning ─────────────────────────────────────────────────────
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "900"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    RETRIEVAL_K: int = int(os.getenv("RETRIEVAL_K", "4"))
    SCORE_THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", "0.05"))

    # ── Convenience flags ──────────────────────────────────────────────
    @property
    def llm_enabled(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY and self.ANTHROPIC_MODEL)


settings = Settings()
