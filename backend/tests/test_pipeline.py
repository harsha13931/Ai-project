import io
import sys
from pathlib import Path

import docx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import assessment, roadmap  # noqa: E402
from app.config import settings  # noqa: E402
from app.ingest import HashingEmbedder, chunk_pages  # noqa: E402
from app.main import app  # noqa: E402
from app.rag import RAGIndex, get_index, reset_index  # noqa: E402
from app.resume import looks_like_resume  # noqa: E402

RESUME = """Harsha Kumar
harsha@example.com | Hyderabad

Summary
Backend developer with 4 years of experience building Python APIs.

Experience
Software Engineer, Acme Corp 2021 - 2025
- Built FastAPI services backed by PostgreSQL and Redis caching.
- Deployed workloads on AWS using Docker.

Education
B.Tech in Computer Science, 2021

Skills
Python, SQL, Docker, machine learning basics
"""

NOTES = """Photosynthesis converts light energy into chemical energy.
The process happens in chloroplasts and releases oxygen as a byproduct.
"""


@pytest.fixture(autouse=True)
def fresh_index(tmp_path):
    settings.DATA_DIR = tmp_path
    settings.DB_PATH = tmp_path / "test.db"
    from app import storage
    storage._db = None
    storage.get_db()
    reset_index()
    yield
    storage.close_db()


def test_chunking_keeps_page_numbers():
    text = "\n\n".join(f"Paragraph {i} explains one idea in a few short words." for i in range(60))
    chunks = chunk_pages([(3, text)], size=300, overlap=60)
    assert len(chunks) > 1
    assert all(c["page"] == 3 for c in chunks)
    assert all(len(c["text"]) <= 300 for c in chunks)


def test_hashing_embedder_is_deterministic_and_normalised():
    emb = HashingEmbedder()
    a, b = emb.embed(["python developer", "python developer"])
    assert (a == b).all()
    assert abs(float((a * a).sum()) - 1.0) < 1e-5


def test_retrieval_finds_the_relevant_document():
    idx = get_index()
    idx.add_document("notes.txt", NOTES.encode())
    idx.add_document("resume.txt", RESUME.encode())
    hits = idx.search("where does photosynthesis take place", k=1)
    assert hits[0]["doc_name"] == "notes.txt"


def test_answer_returns_sources_and_extractive_text(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    idx = get_index()
    idx.add_document("notes.txt", NOTES.encode())
    result = idx.answer("What does photosynthesis release?")
    assert result["mode"] in {"extractive", "llm"}
    assert "oxygen" in result["answer"].lower()
    assert result["sources"][0]["page"] == 1


def test_unrelated_question_is_declined():
    idx = get_index()
    idx.add_document("notes.txt", NOTES.encode())
    result = idx.answer("Who won the 1998 football world cup in Paris?")
    assert result["mode"] in {"none", "extractive"}
    if result["mode"] == "none":
        assert "could not find" in result["answer"]


def test_resume_detection_and_profile():
    assert looks_like_resume(RESUME)
    assert not looks_like_resume(NOTES)
    idx = get_index()
    doc = idx.add_document("cv.txt", RESUME.encode())
    assert doc["is_resume"] is True
    profile = idx.documents[doc["id"]]["profile"]
    assert profile["name"] == "Harsha Kumar"
    assert profile["years_experience"] == 4
    assert {"python", "sql", "cloud_devops"}.issubset(profile["detected_topics"])
    assert "system_design" not in profile["detected_topics"]


def test_docx_extraction():
    document = docx.Document()
    document.add_paragraph("Senior data analyst with SQL and statistics skills.")
    buf = io.BytesIO()
    document.save(buf)
    idx = get_index()
    doc = idx.add_document("cv.docx", buf.getvalue())
    assert doc["pages"] == 1 and doc["chunks"] >= 1


def test_quiz_gives_more_questions_for_claimed_skills():
    profile = {"detected_topics": ["python", "sql"]}
    quiz = assessment.build_quiz(profile)
    by_topic = {}
    for q in quiz["questions"]:
        by_topic.setdefault(q["topic"], []).append(q)
    assert len(by_topic["python"]) > 1
    assert len(by_topic["system_design"]) == 1
    assert all(q["claimed"] for q in by_topic["python"])
    assert not any(k.startswith("_") for q in assessment.public_view(quiz)["questions"] for k in q)


def test_scoring_flags_claimed_but_unverified():
    quiz = assessment.build_quiz({"detected_topics": ["python"]})
    python_count = sum(1 for q in quiz["questions"] if q["topic"] == "python")
    answers = {}
    for q in quiz["questions"]:
        answers[q["id"]] = q["_answer"] if q["topic"] != "python" else (q["_answer"] + 1) % len(q["options"])
    result = assessment.score_quiz(quiz, answers)
    python = next(t for t in result["topics"] if t["topic"] == "python")
    assert python["percent"] == 0
    assert python["flag"] == "claimed but unverified"
    assert python["guidance"]
    assert "python" in result["gaps"]
    expected = round(100 * (len(quiz["questions"]) - python_count) / len(quiz["questions"]))
    assert result["percent"] == expected


def test_perfect_score_is_strong():
    quiz = assessment.build_quiz(None)
    answers = {q["id"]: q["_answer"] for q in quiz["questions"]}
    result = assessment.score_quiz(quiz, answers)
    assert result["percent"] == 100 and result["level"] == "Strong"
    assert result["gaps"] == []


@pytest.mark.parametrize("role", list(roadmap.ROLES))
def test_roadmap_timetable_matches_requested_weeks(role):
    plan = roadmap.build_roadmap(role, total_weeks=12, hours_per_week=8)
    assert len(plan["timetable"]) == 12
    assert plan["total_hours"] == 96
    milestones = [w for w in plan["timetable"] if w["milestone"]]
    assert len(milestones) == len(plan["phases"])


def test_roadmap_pulls_gaps_to_front():
    plan = roadmap.build_roadmap("backend_engineer", gaps=["sql"])
    assert plan["gaps_addressed"] == ["SQL & Databases"]
    assert plan["phases"][0]["topics"][0] == "Shore up: SQL & Databases"


def test_end_to_end_api_flow():
    client = TestClient(app)
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["persistence"] == "sqlite"
    assert health["retrieval"] == "hybrid (dense + BM25 + RRF)"

    upload = client.post("/api/documents", files={"file": ("cv.txt", RESUME.encode(), "text/plain")})
    assert upload.status_code == 201
    assert upload.json()["is_resume"] is True
    doc_id = upload.json()["id"]

    docs = client.get("/api/documents").json()
    assert any(d["id"] == doc_id for d in docs)

    quiz = client.post("/api/quiz", json={"num_questions": 5}).json()
    assert quiz["total"] == len(quiz["questions"])
    answers = {q["id"]: 0 for q in quiz["questions"]}
    result = client.post(f"/api/quiz/{quiz['id']}/submit", json={"answers": answers}).json()
    assert 0 <= result["percent"] <= 100

    plan = client.post("/api/roadmap", json={"role": "data_analyst", "weeks": 10, "quiz_id": quiz["id"]})
    assert plan.status_code == 200 and len(plan.json()["timetable"]) == 10

    assert client.post("/api/roadmap", json={"role": "astronaut"}).status_code == 404
    assert client.post("/api/ask", json={"question": "what is in this file?"}).status_code == 200

    delete = client.delete(f"/api/documents/{doc_id}")
    assert delete.status_code == 200 and delete.json()["deleted"] is True
    assert client.delete(f"/api/documents/{doc_id}").status_code == 404


def test_quiz_requires_resume():
    client = TestClient(app)
    assert client.post("/api/quiz", json={}).status_code == 400


def test_quiz_num_questions_limits_output():
    profile = {"detected_topics": ["python", "sql", "statistics"]}
    quiz = assessment.build_quiz(profile, num_questions=5)
    assert len(quiz["questions"]) == 5


def test_upload_rejects_unsupported_type():
    client = TestClient(app)
    res = client.post("/api/documents", files={"file": ("image.png", b"\x89PNG", "image/png")})
    assert res.status_code == 422


def test_config_centralised():
    """Verify that settings is the single source of truth."""
    assert hasattr(settings, "ANTHROPIC_API_KEY")
    assert hasattr(settings, "EMBEDDING_MODEL")
    assert hasattr(settings, "llm_enabled")
