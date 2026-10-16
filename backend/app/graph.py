"""LangGraph workflows for the three main pipelines.

Each graph is a compiled ``StateGraph`` that can be invoked with
``graph.invoke(state)``.  The graphs handle branching (e.g. resume vs
plain document) and fallback (LLM unavailable → rule-based).
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from . import assessment as assess_mod
from . import roadmap as roadmap_mod
from .chains import (
    guidance_chain,
    parse_llm_json,
    quiz_generation_chain,
    rag_chain,
    resume_analysis_chain,
    roadmap_chain,
)
from .config import settings
from .knowledge import TOPICS

log = logging.getLogger(__name__)


# ======================================================================
# 1.  RAG answering graph
# ======================================================================

class RAGState(TypedDict, total=False):
    question: str
    doc_id: str | None
    hits: list[dict]
    answer: str
    mode: str
    sources: list[dict]


def _rag_retrieve(state: RAGState) -> dict:
    from .rag import get_index

    idx = get_index()
    raw_hits = idx.search(state["question"], k=settings.RETRIEVAL_K, doc_id=state.get("doc_id"))
    threshold = settings.SCORE_THRESHOLD
    if raw_hits and raw_hits[0]["score"] < 0.1:
        threshold = min(threshold, 0.005)
    hits = [h for h in raw_hits if h["score"] > threshold]
    sources = [
        {"doc": h["doc_name"], "page": h["page"], "score": h["score"], "excerpt": h["text"][:240]}
        for h in hits
    ]
    return {"hits": hits, "sources": sources}


def _rag_no_hits(state: RAGState) -> dict:
    return {
        "answer": "I could not find that in the uploaded documents.",
        "mode": "none",
        "sources": [],
    }


def _rag_llm_answer(state: RAGState) -> dict:
    chain = rag_chain()
    if chain is None:
        return _rag_extractive(state)
    context = "\n\n".join(
        f"[{i + 1}] (page {h['page']}) {h['text']}" for i, h in enumerate(state["hits"])
    )
    try:
        answer = chain.invoke({"context": context, "question": state["question"]})
        return {"answer": answer, "mode": "llm"}
    except Exception:
        log.exception("LLM answering failed, falling back to extractive")
        return _rag_extractive(state)


def _rag_extractive(state: RAGState) -> dict:
    from .rag import get_index

    idx = get_index()
    answer = idx._extractive_answer(state["question"], state["hits"])
    return {"answer": answer, "mode": "extractive"}


def _has_hits(state: RAGState) -> str:
    return "answer" if state.get("hits") else "no_hits"


def build_rag_graph() -> StateGraph:
    g = StateGraph(RAGState)
    g.add_node("retrieve", _rag_retrieve)
    g.add_node("no_hits", _rag_no_hits)
    g.add_node("answer", _rag_llm_answer)
    g.set_entry_point("retrieve")
    g.add_conditional_edges("retrieve", _has_hits, {"answer": "answer", "no_hits": "no_hits"})
    g.add_edge("no_hits", END)
    g.add_edge("answer", END)
    return g.compile()


# ======================================================================
# 2.  Document processing graph
# ======================================================================

class DocState(TypedDict, total=False):
    filename: str
    data: bytes
    doc_id: str
    doc_info: dict
    is_resume: bool
    profile: dict | None


def _ingest_document(state: DocState) -> dict:
    from .rag import get_index

    idx = get_index()
    doc_info = idx.add_document(state["filename"], state["data"])
    doc = idx.documents[doc_info["id"]]
    return {
        "doc_id": doc_info["id"],
        "doc_info": doc_info,
        "is_resume": doc_info["is_resume"],
        "profile": doc.get("profile"),
    }


def _enhance_profile(state: DocState) -> dict:
    """Use LLM to enrich the resume profile when available."""
    chain = resume_analysis_chain()
    if chain is None or not state.get("is_resume"):
        return {}
    from .rag import get_index

    idx = get_index()
    text = idx.documents[state["doc_id"]]["text"]
    try:
        raw = chain.invoke({"resume_text": text[:4000]})
        enriched = parse_llm_json(raw)
        profile = state.get("profile") or {}
        if isinstance(enriched, dict):
            profile["llm_summary"] = enriched.get("summary", "")
            if enriched.get("detected_topics"):
                existing = set(profile.get("detected_topics", []))
                for t in enriched["detected_topics"]:
                    if t in TOPICS:
                        existing.add(t)
                profile["detected_topics"] = list(existing)
                profile["claimed_skills"] = [TOPICS[t]["label"] for t in profile["detected_topics"]]
        idx.documents[state["doc_id"]]["profile"] = profile
        return {"profile": profile}
    except Exception:
        log.exception("LLM resume enrichment failed, keeping rule-based profile")
        return {}


def _should_enhance(state: DocState) -> str:
    return "enhance" if state.get("is_resume") and settings.llm_enabled else "done"


def build_doc_graph() -> StateGraph:
    g = StateGraph(DocState)
    g.add_node("ingest", _ingest_document)
    g.add_node("enhance", _enhance_profile)
    g.set_entry_point("ingest")
    g.add_conditional_edges("ingest", _should_enhance, {"enhance": "enhance", "done": END})
    g.add_edge("enhance", END)
    return g.compile()


# ======================================================================
# 3.  Career coaching graph  (quiz → score → roadmap)
# ======================================================================

class CoachState(TypedDict, total=False):
    profile: dict
    resume_text: str
    num_questions: int
    quiz: dict
    quiz_public: dict
    answers: dict[str, int]
    result: dict
    role: str
    weeks: int
    hours_per_week: int
    roadmap: dict
    llm_guidance: str | None


def _build_quiz(state: CoachState) -> dict:
    """Generate quiz dynamically from resume via LLM, fall back to static bank."""
    profile = state["profile"]
    num_questions = state.get("num_questions", 10)
    resume_text = state.get("resume_text", "")
    chain = quiz_generation_chain()
    if chain is not None and resume_text:
        try:
            raw = chain.invoke({
                "resume_text": resume_text[:6000],
                "profile": str(profile),
                "num_questions": str(num_questions),
            })
            questions = parse_llm_json(raw)
            if isinstance(questions, list) and len(questions) >= 2:
                import uuid
                for q in questions:
                    q["id"] = uuid.uuid4().hex[:8]
                    q.setdefault("claimed", True)
                    q["_answer"] = q.pop("answer", 0)
                    q["_explain"] = q.pop("explain", "")
                quiz = {"id": uuid.uuid4().hex[:12], "questions": questions, "profile": profile}
                log.info("LLM generated %d dynamic questions from resume", len(questions))
                return {"quiz": quiz, "quiz_public": assess_mod.public_view(quiz)}
        except Exception:
            log.exception("LLM quiz generation failed, using static fallback")

    quiz = assess_mod.build_quiz(profile, num_questions)
    return {"quiz": quiz, "quiz_public": assess_mod.public_view(quiz)}


def _score_quiz(state: CoachState) -> dict:
    result = assess_mod.score_quiz(state["quiz"], state["answers"])
    guidance = None
    chain = guidance_chain()
    if chain is not None:
        try:
            guidance = chain.invoke({"results": str(result)})
        except Exception:
            log.exception("LLM guidance failed")
    if guidance:
        result["llm_guidance"] = guidance
    return {"result": result, "llm_guidance": guidance}


def _build_roadmap(state: CoachState) -> dict:
    role_key = state["role"]
    weeks = state.get("weeks", 12)
    hours = state.get("hours_per_week", 10)
    gaps = state.get("result", {}).get("gaps", [])

    chain = roadmap_chain()
    if chain is not None:
        try:
            role_info = roadmap_mod.ROLES[role_key]
            raw = chain.invoke({
                "role": role_info["label"],
                "weeks": str(weeks),
                "hours": str(hours),
                "gaps": str([TOPICS[g]["label"] for g in gaps if g in TOPICS]),
                "role_description": role_info["summary"],
            })
            llm_roadmap = parse_llm_json(raw)
            if isinstance(llm_roadmap, dict) and "phases" in llm_roadmap:
                llm_roadmap.setdefault("role", role_info["label"])
                llm_roadmap.setdefault("summary", role_info["summary"])
                llm_roadmap.setdefault("total_weeks", weeks)
                llm_roadmap.setdefault("hours_per_week", hours)
                llm_roadmap.setdefault("total_hours", weeks * hours)
                llm_roadmap.setdefault("gaps_addressed", [TOPICS[g]["label"] for g in gaps if g in TOPICS])
                return {"roadmap": llm_roadmap}
        except Exception:
            log.exception("LLM roadmap generation failed, using rule-based")

    return {"roadmap": roadmap_mod.build_roadmap(role_key, weeks, hours, gaps)}


# We don't compile a single coaching graph because quiz → score → roadmap
# are separate API calls.  Instead export node functions for main.py.
