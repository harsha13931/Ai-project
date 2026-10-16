"""FastAPI service: document ingestion, Q&A, resume assessment, and roadmap."""
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import assessment, roadmap
from .rag import RAGIndex

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="Doc RAG & Career Coach", version="1.0.0")
index = RAGIndex()  # single-process store; swap for pgvector/Qdrant in production
quizzes: dict[str, dict] = {}


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
    try:
        return index.add_document(file.filename or "upload.txt", data)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/documents")
def list_documents():
    return [index.public_doc(doc_id) for doc_id in index.documents]


@app.post("/api/ask")
def ask(body: AskRequest):
    if body.doc_id and body.doc_id not in index.documents:
        raise HTTPException(404, "Document not found.")
    return index.answer(body.question, body.doc_id)


@app.post("/api/quiz", status_code=201)
def create_quiz(doc_id: str | None = None):
    resumes = [d for d in index.documents.values() if d["is_resume"]]
    if doc_id:
        doc = index.documents.get(doc_id)
        if not doc:
            raise HTTPException(404, "Document not found.")
        if not doc["is_resume"]:
            raise HTTPException(400, "This document does not look like a resume.")
        profile = doc["profile"]
    elif resumes:
        profile = resumes[-1]["profile"]
    else:
        raise HTTPException(400, "Upload a resume first so the assessment can be personalised.")

    quiz = assessment.build_quiz(profile)
    quizzes[quiz["id"]] = quiz
    return assessment.public_view(quiz)


@app.post("/api/quiz/{quiz_id}/submit")
def submit_quiz(quiz_id: str, body: SubmitRequest):
    quiz = quizzes.get(quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    result = assessment.score_quiz(quiz, body.answers)
    quiz["result"] = result
    return result


@app.get("/api/roles")
def roles():
    return roadmap.role_options()


@app.post("/api/roadmap")
def create_roadmap(body: RoadmapRequest):
    if body.role not in roadmap.ROLES:
        raise HTTPException(404, "Unknown role.")
    gaps = []
    if body.quiz_id:
        quiz = quizzes.get(body.quiz_id)
        if not quiz:
            raise HTTPException(404, "Quiz not found.")
        if "result" not in quiz:
            raise HTTPException(400, "Submit the assessment before building a roadmap from it.")
        gaps = quiz["result"]["gaps"]
    return roadmap.build_roadmap(body.role, body.weeks, body.hours_per_week, gaps)


@app.get("/api/health")
def health():
    return {"status": "ok", "chunks": len(index.chunks), "documents": len(index.documents)}


@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
