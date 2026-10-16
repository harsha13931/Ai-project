"""LangChain chain factories — one builder per pipeline stage.

Every chain reads its config from ``config.settings`` so API keys live in
exactly one place.  When the LLM is not configured the helpers return
``None`` and callers fall back to rule-based logic.
"""
from __future__ import annotations

import json
import logging
from typing import Any

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

_llm = None


def get_llm():
    """Return a ChatAnthropic instance or *None* if no API key is set."""
    global _llm
    if _llm is not None:
        return _llm
    if not settings.llm_enabled:
        return None
    from langchain_anthropic import ChatAnthropic

    _llm = ChatAnthropic(
        model=settings.ANTHROPIC_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=1024,
        temperature=0.3,
    )
    return _llm


# ── Chain builders ─────────────────────────────────────────────────────

def rag_chain():
    """Retrieval-augmented QA chain.  Returns *None* when LLM is off."""
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
