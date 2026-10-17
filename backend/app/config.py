"""Centralised configuration — every API key and setting in one place.

Set values via environment variables or a .env file.  The rest of the app
imports ``settings`` from here and never reads os.environ directly.

Supported LLM providers (set LLM_PROVIDER or just set the API key):
  anthropic  — Claude (ANTHROPIC_API_KEY)
  openai     — GPT-4o, GPT-4, etc. (OPENAI_API_KEY)
  google     — Gemini (GOOGLE_API_KEY)
  groq       — Groq (GROQ_API_KEY)
  mistral    — Mistral (MISTRAL_API_KEY)
  openai_compatible — Any OpenAI-compatible endpoint (OPENAI_API_KEY + OPENAI_BASE_URL)
"""
import os
from pathlib import Path


def _detect_provider() -> str:
    """Auto-detect LLM provider from whichever API key is set."""
    explicit = os.getenv("LLM_PROVIDER", "").lower()
    if explicit:
        return explicit
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_BASE_URL"):
        return "openai_compatible"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GOOGLE_API_KEY"):
        return "google"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("MISTRAL_API_KEY"):
        return "mistral"
    return ""


_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "mistral": "mistral-large-latest",
    "openai_compatible": "gpt-4o",
}


class Settings:
    # ── LLM (multi-provider) ──────────────────────────────────────────
    LLM_PROVIDER: str = _detect_provider()
    LLM_MODEL: str = os.getenv(
        "LLM_MODEL",
        os.getenv("ANTHROPIC_MODEL", "")
        or _DEFAULT_MODELS.get(_detect_provider(), ""),
    )

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")

    # Back-compat: ANTHROPIC_MODEL still works
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "")

    # ── Embeddings (HuggingFace — free, local, no API key) ────────────
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")

    # ── RAG tuning ────────────────────────────────────────────────────
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "900"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    RETRIEVAL_K: int = int(os.getenv("RETRIEVAL_K", "4"))
    SCORE_THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", "0.05"))

    # ── Persistence ───────────────────────────────────────────────────
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
    DB_PATH: Path = Path(os.getenv("DB_PATH", "")) or DATA_DIR / "docmind.db"
    FAISS_DIR: Path = Path(os.getenv("FAISS_DIR", "")) or DATA_DIR / "faiss_index"

    # ── Security ──────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    RATE_LIMIT: str = os.getenv("RATE_LIMIT", "30/minute")
    RATE_LIMIT_UPLOAD: str = os.getenv("RATE_LIMIT_UPLOAD", "10/minute")
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    DOC_RETENTION_HOURS: int = int(os.getenv("DOC_RETENTION_HOURS", "0"))

    # ── Convenience flags ─────────────────────────────────────────────
    @property
    def llm_enabled(self) -> bool:
        return bool(self.LLM_PROVIDER and self.LLM_MODEL)


settings = Settings()
