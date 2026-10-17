"""LangChain chain factories — one builder per pipeline stage.

Every chain reads its config from ``config.settings`` so API keys live in
exactly one place.  When the LLM is not configured the helpers return
``None`` and callers fall back to rule-based logic.

Supports multiple providers: Anthropic, OpenAI, Google Gemini, Groq,
Mistral, and any OpenAI-compatible endpoint.  Just set the right API
key — the provider is auto-detected.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from .config import settings
from .prompts import (
    GUIDANCE_PROMPT,
    QUIZ_GENERATION_PROMPT,
    RAG_PROMPT,
    RESUME_ANALYSIS_PROMPT,
    ROADMAP_PROMPT,
)

log = logging.getLogger(__name__)

# ── Shared LLM singleton ──────────────────────────────────────────────

_llm: BaseChatModel | None = None


def _build_llm() -> BaseChatModel | None:
    """Build the right LangChain chat model for the configured provider."""
    provider = settings.LLM_PROVIDER
    model = settings.LLM_MODEL

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=1024,
            temperature=0.3,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=1024,
            temperature=0.3,
        )

    if provider == "openai_compatible":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            max_tokens=1024,
            temperature=0.3,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
            max_output_tokens=1024,
            temperature=0.3,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            api_key=settings.GROQ_API_KEY,
            max_tokens=1024,
            temperature=0.3,
        )

    if provider == "mistral":
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(
            model=model,
            api_key=settings.MISTRAL_API_KEY,
            max_tokens=1024,
            temperature=0.3,
        )

    return None


def get_llm() -> BaseChatModel | None:
    """Return the configured chat model or *None* if no API key is set."""
    global _llm
    if _llm is not None:
        return _llm
    if not settings.llm_enabled:
        return None
    try:
        _llm = _build_llm()
        if _llm is not None:
            log.info("LLM ready: provider=%s model=%s", settings.LLM_PROVIDER, settings.LLM_MODEL)
    except ImportError as exc:
        log.warning(
            "LLM provider '%s' requires an extra package: %s  "
            "(pip install langchain-%s)",
            settings.LLM_PROVIDER, exc, settings.LLM_PROVIDER,
        )
    except Exception:
        log.exception("Failed to initialise LLM provider '%s'", settings.LLM_PROVIDER)
    return _llm


def reset_llm() -> None:
    """Clear the cached LLM so the next call to get_llm() rebuilds it."""
    global _llm
    _llm = None


# ── Chain builders ─────────────────────────────────────────────────────

def rag_chain():
    llm = get_llm()
    if llm is None:
        return None
    return RAG_PROMPT | llm | StrOutputParser()


def resume_analysis_chain():
    llm = get_llm()
    if llm is None:
        return None
    return RESUME_ANALYSIS_PROMPT | llm | StrOutputParser()


def quiz_generation_chain():
    llm = get_llm()
    if llm is None:
        return None
    return QUIZ_GENERATION_PROMPT | llm | StrOutputParser()


def guidance_chain():
    llm = get_llm()
    if llm is None:
        return None
    return GUIDANCE_PROMPT | llm | StrOutputParser()


def roadmap_chain():
    llm = get_llm()
    if llm is None:
        return None
    return ROADMAP_PROMPT | llm | StrOutputParser()


# ── Helper: safe JSON parse from LLM output ───────────────────────────

def parse_llm_json(text: str) -> Any:
    """Strip markdown fences and parse JSON from an LLM response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    return json.loads(cleaned)
