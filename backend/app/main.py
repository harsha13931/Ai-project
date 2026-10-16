"""FastAPI service with LangChain + LangGraph powered pipelines.

All configuration (API keys, model names) comes from ``config.settings``
— set your keys in environment variables or a .env file, ONE place.
"""
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import assessment, roadmap
from .config import settings
from .rag import get_index, reset_index

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="DocMind — RAG & Career Coach", version="2.0.0")
quizzes: dict[str, dict] = {}

# Lazy-import the LangGraph workflows so the app starts even if
# langgraph is not installed.
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


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    doc_id: str | None = None


class SubmitRequest(BaseModel):
    answers: dict[str, int]


class RoadmapRequest(BaseModel):
    role: str
    weeks: int = Field(default=12, ge=4, le=26)
    hours_per_week: int = Field(default=10, ge=2, le=40)
    quiz_id: str | None = None


@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")

    graph = _get_doc_graph()
    if graph is not None:
        try:
            result = graph.invoke({"filename": file.filename or "upload.txt", "data": data})
            return result["doc_info"]
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except Exception:
            pass  # fall through to direct path

    try:
        return get_index().add_document(file.filename or "upload.txt", data)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/documents")
def list_documents():
    idx = get_index()
    return [idx.public_doc(doc_id) for doc_id in idx.documents]


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
            pass  # fall through

    return idx.answer(body.question, body.doc_id)


@app.post("/api/quiz", status_code=201)
def create_quiz(doc_id: str | None = None):
    idx = get_index()
    resumes = [d for d in idx.documents.values() if d["is_resume"]]
    if doc_id:
        doc = idx.documents.get(doc_id)
        if not doc:
            raise HTTPException(404, "Document not found.")
        if not doc["is_resume"]:
            raise HTTPException(400, "This document does not look like a resume.")
        profile = doc["profile"]
    elif resumes:
        profile = resumes[-1]["profile"]
    else:
        raise HTTPException(400, "Upload a resume first so the assessment can be personalised.")

    try:
        from .graph import _build_quiz
        result = _build_quiz({"profile": profile})
        quiz = result["quiz"]
    except ImportError:
        quiz = assessment.build_quiz(profile)

    quizzes[quiz["id"]] = quiz
    return assessment.public_view(quiz)


@app.post("/api/quiz/{quiz_id}/submit")
def submit_quiz(quiz_id: str, body: SubmitRequest):
    quiz = quizzes.get(quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found.")

    try:
        from .graph import _score_quiz
        result = _score_quiz({"quiz": quiz, "answers": body.answers})
        score_result = result["result"]
    except ImportError:
        score_result = assessment.score_quiz(quiz, body.answers)

    quiz["result"] = score_result
    return score_result


@app.get("/api/roles")
def roles():
    return roadmap.role_options()


@app.post("/api/roadmap")
def create_roadmap(body: RoadmapRequest):
    if body.role not in roadmap.ROLES:
        raise HTTPException(404, "Unknown role.")

    gaps: list[str] = []
    if body.quiz_id:
        quiz = quizzes.get(body.quiz_id)
        if not quiz:
            raise HTTPException(404, "Quiz not found.")
        if "result" not in quiz:
            raise HTTPException(400, "Submit the assessment before building a roadmap from it.")
        gaps = quiz["result"]["gaps"]

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


@app.get("/api/health")
def health():
    idx = get_index()
    return {
        "status": "ok",
        "chunks": len(idx.chunks),
        "documents": len(idx.documents),
        "embeddings": settings.EMBEDDING_MODEL,
        "llm_enabled": settings.llm_enabled,
    }


@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
