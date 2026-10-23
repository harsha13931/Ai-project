"""FastAPI service with LangChain + LangGraph powered pipelines.

Production-grade: SQLite persistence, hybrid retrieval, security
middleware, structured lifecycle.  All configuration comes from
``config.settings`` — set keys in environment variables or a .env file.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import assessment, roadmap, storage
from .config import settings
from .rag import get_index, reset_index
from .security import add_security

log = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

# ── LangGraph lazy init ──────────────────────────────────────────────

_doc_graph = None
_rag_graph = None


def _get_doc_graph():
    global _doc_graph
    if _doc_graph is None:
        try:
            from .graph import build_doc_graph
            _doc_graph = build_doc_graph()
        except ImportError:
            pass
    return _doc_graph


def _get_rag_graph():
    global _rag_graph
    if _rag_graph is None:
        try:
            from .graph import build_rag_graph
            _rag_graph = build_rag_graph()
        except ImportError:
            pass
    return _rag_graph


# ── Lifecycle ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    storage.get_db()
    _restore_documents()
    purged = storage.purge_expired()
    if purged:
        log.info("Purged %d expired documents", purged)
    log.info(
        "DocMind ready — LLM %s, embeddings=%s, docs=%d",
        "enabled" if settings.llm_enabled else "disabled",
        settings.EMBEDDING_MODEL,
        len(get_index().documents),
    )
    yield
    storage.close_db()


def _restore_documents():
    """Reload persisted documents into the in-memory RAG index on startup."""
    idx = get_index()
    rows = storage.load_documents()
    restored = 0
    for row in rows:
        if row["id"] in idx.documents:
            continue
        idx.documents[row["id"]] = {
            "id": row["id"],
            "name": row["name"],
            "pages": row["pages"],
            "chunks": row["chunks"],
            "is_resume": row["is_resume"],
            "profile": row.get("profile"),
            "text": row.get("text", ""),
        }
        restored += 1
    if restored:
        log.info("Restored %d documents from database", restored)


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="DocMind — RAG & Career Coach",
    version="3.0.0",
    lifespan=lifespan,
)

add_security(app)

# ── Request models ───────────────────────────────────────────────────


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    doc_id: str | None = None


class SubmitRequest(BaseModel):
    answers: dict[str, int]


class QuizRequest(BaseModel):
    doc_id: str | None = None
    num_questions: int = Field(default=10, ge=3, le=50)


class RoadmapRequest(BaseModel):
    role: str
    weeks: int = Field(default=12, ge=4, le=26)
    hours_per_week: int = Field(default=10, ge=2, le=40)
    quiz_id: str | None = None


# ── Document endpoints ───────────────────────────────────────────────

@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            f"File is larger than {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    graph = _get_doc_graph()
    if graph is not None:
        try:
            result = graph.invoke({"filename": file.filename or "upload.txt", "data": data})
            doc_info = result["doc_info"]
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except Exception:
            log.exception("Doc graph failed, falling back to direct ingest")
            doc_info = None

    if graph is None or doc_info is None:
        try:
            doc_info = get_index().add_document(file.filename or "upload.txt", data)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    idx = get_index()
    doc = idx.documents.get(doc_info["id"])
    if doc:
        storage.save_document(doc)

    return doc_info


@app.get("/api/documents")
def list_documents():
    idx = get_index()
    return [idx.public_doc(doc_id) for doc_id in idx.documents]


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    idx = get_index()
    if doc_id not in idx.documents:
        raise HTTPException(404, "Document not found.")
    del idx.documents[doc_id]
    storage.delete_document(doc_id)
    return {"deleted": True}


# ── Ask endpoint ─────────────────────────────────────────────────────

@app.post("/api/ask")
def ask(body: AskRequest):
    idx = get_index()
    if body.doc_id and body.doc_id not in idx.documents:
        raise HTTPException(404, "Document not found.")

    graph = _get_rag_graph()
    if graph is not None:
        try:
            result = graph.invoke({"question": body.question, "doc_id": body.doc_id})
            return {
                "answer": result.get("answer", ""),
                "mode": result.get("mode", "none"),
                "sources": result.get("sources", []),
            }
        except Exception:
            log.exception("RAG graph failed, falling back to direct answer")

    return idx.answer(body.question, body.doc_id)


# ── Quiz endpoints ───────────────────────────────────────────────────

@app.post("/api/quiz", status_code=201)
def create_quiz(body: QuizRequest | None = None):
    doc_id = body.doc_id if body else None
    num_questions = body.num_questions if body else 10

    idx = get_index()
    resumes = [d for d in idx.documents.values() if d["is_resume"]]
    if doc_id:
        doc = idx.documents.get(doc_id)
        if not doc:
            raise HTTPException(404, "Document not found.")
        if not doc["is_resume"]:
            raise HTTPException(400, "This document does not look like a resume.")
    elif resumes:
        doc = resumes[-1]
    else:
        raise HTTPException(400, "Upload a resume first so the assessment can be personalised.")

    profile = doc["profile"]
    resume_text = doc.get("text", "")

    try:
        from .graph import _build_quiz
        result = _build_quiz({
            "profile": profile,
            "resume_text": resume_text,
            "num_questions": num_questions,
        })
        quiz = result["quiz"]
    except ImportError:
        quiz = assessment.build_quiz(profile, num_questions)

    storage.save_quiz(quiz)
    return assessment.public_view(quiz)


@app.post("/api/quiz/{quiz_id}/submit")
def submit_quiz(quiz_id: str, body: SubmitRequest):
    quiz = storage.load_quiz(quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found.")

    try:
        from .graph import _score_quiz
        result = _score_quiz({"quiz": quiz, "answers": body.answers})
        score_result = result["result"]
    except ImportError:
        score_result = assessment.score_quiz(quiz, body.answers)

    storage.save_quiz_result(quiz_id, score_result)
    return score_result


# ── Roadmap endpoints ────────────────────────────────────────────────

@app.get("/api/roles")
def roles():
    return roadmap.role_options()


@app.post("/api/roadmap")
def create_roadmap(body: RoadmapRequest):
    if body.role not in roadmap.ROLES:
        raise HTTPException(404, "Unknown role.")

    gaps: list[str] = []
    if body.quiz_id:
        quiz = storage.load_quiz(body.quiz_id)
        if not quiz:
            raise HTTPException(404, "Quiz not found.")
        result = quiz.get("result")
        if not result:
            raise HTTPException(400, "Submit the assessment before building a roadmap from it.")
        gaps = result["gaps"]

    try:
        from .graph import _build_roadmap
        result = _build_roadmap({
            "role": body.role,
            "weeks": body.weeks,
            "hours_per_week": body.hours_per_week,
            "result": {"gaps": gaps},
        })
        return result["roadmap"]
    except ImportError:
        return roadmap.build_roadmap(body.role, body.weeks, body.hours_per_week, gaps)


# ── Health & info ────────────────────────────────────────────────────

@app.get("/api/pipeline-graph")
def pipeline_graph():
    """Return the LangGraph pipeline topology for visualization."""
    return {
        "graphs": [
            {
                "id": "rag",
                "label": "RAG Answering",
                "description": "Retrieves relevant chunks and generates an answer",
                "nodes": [
                    {"id": "question", "label": "Question", "type": "input"},
                    {"id": "retrieve", "label": "Hybrid Retrieve", "type": "process",
                     "detail": "Dense (FAISS) + BM25 lexical search, fused with Reciprocal Rank Fusion"},
                    {"id": "has_hits", "label": "Has Hits?", "type": "condition"},
                    {"id": "answer", "label": "LLM Answer", "type": "process",
                     "detail": "LangChain LLM generates answer from retrieved context with citations"},
                    {"id": "no_hits", "label": "No Results", "type": "fallback",
                     "detail": "Returns a polite decline when no relevant chunks found"},
                    {"id": "end_rag", "label": "Response", "type": "output"},
                ],
                "edges": [
                    {"from": "question", "to": "retrieve"},
                    {"from": "retrieve", "to": "has_hits"},
                    {"from": "has_hits", "to": "answer", "label": "yes"},
                    {"from": "has_hits", "to": "no_hits", "label": "no"},
                    {"from": "answer", "to": "end_rag"},
                    {"from": "no_hits", "to": "end_rag"},
                ],
            },
            {
                "id": "doc",
                "label": "Document Processing",
                "description": "Ingests a file, detects resumes, and enriches profiles",
                "nodes": [
                    {"id": "upload", "label": "File Upload", "type": "input"},
                    {"id": "ingest", "label": "Ingest & Chunk", "type": "process",
                     "detail": "Extract text, split into overlapping chunks, embed with HuggingFace, index in FAISS + BM25"},
                    {"id": "is_resume", "label": "Is Resume?", "type": "condition"},
                    {"id": "enhance", "label": "LLM Enrich", "type": "process",
                     "detail": "LLM analyses resume for skills, topics, summary"},
                    {"id": "persist", "label": "SQLite Persist", "type": "output",
                     "detail": "Document and profile saved to SQLite for server restart survival"},
                ],
                "edges": [
                    {"from": "upload", "to": "ingest"},
                    {"from": "ingest", "to": "is_resume"},
                    {"from": "is_resume", "to": "enhance", "label": "yes"},
                    {"from": "is_resume", "to": "persist", "label": "no"},
                    {"from": "enhance", "to": "persist"},
                ],
            },
            {
                "id": "coach",
                "label": "Career Coaching",
                "description": "Quiz generation, scoring, and roadmap planning",
                "nodes": [
                    {"id": "resume", "label": "Resume Profile", "type": "input"},
                    {"id": "quiz_gen", "label": "Generate Quiz", "type": "process",
                     "detail": "LLM creates questions from resume text; static bank as fallback"},
                    {"id": "score", "label": "Score & Analyse", "type": "process",
                     "detail": "Checks answers, flags claimed-but-unverified skills, finds gaps"},
                    {"id": "guidance", "label": "LLM Guidance", "type": "process",
                     "detail": "Personalised study advice from the LLM based on score results"},
                    {"id": "roadmap_gen", "label": "Build Roadmap", "type": "process",
                     "detail": "Week-by-week plan prioritising gaps, with milestones"},
                    {"id": "plan", "label": "Learning Plan", "type": "output"},
                ],
                "edges": [
                    {"from": "resume", "to": "quiz_gen"},
                    {"from": "quiz_gen", "to": "score"},
                    {"from": "score", "to": "guidance"},
                    {"from": "guidance", "to": "roadmap_gen"},
                    {"from": "roadmap_gen", "to": "plan"},
                ],
            },
        ],
        "meta": {
            "framework": "LangGraph StateGraph",
            "embeddings": settings.EMBEDDING_MODEL,
            "vector_store": "FAISS",
            "lexical": "BM25 (Okapi)",
            "fusion": "Reciprocal Rank Fusion",
            "persistence": "SQLite",
            "llm_provider": settings.LLM_PROVIDER or "none",
            "llm_model": settings.LLM_MODEL or "none",
        },
    }


@app.get("/api/health")
def health():
    idx = get_index()
    return {
        "status": "ok",
        "version": "3.0.0",
        "chunks": len(idx.chunks),
        "documents": len(idx.documents),
        "embeddings": settings.EMBEDDING_MODEL,
        "llm_enabled": settings.llm_enabled,
        "llm_provider": settings.LLM_PROVIDER or "none",
        "llm_model": settings.LLM_MODEL or "none",
        "persistence": "sqlite",
        "retrieval": "hybrid (dense + BM25 + RRF)",
    }


# ── Static files ─────────────────────────────────────────────────────

@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
