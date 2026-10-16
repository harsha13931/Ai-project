"""SQLite persistence for documents, quizzes, and metadata.

Documents and quiz results survive server restarts.  The vector index
is persisted separately by FAISS (see rag.py).
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .config import settings

_db: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    pages       INTEGER NOT NULL,
    chunks      INTEGER NOT NULL,
    is_resume   INTEGER NOT NULL DEFAULT 0,
    profile     TEXT,
    full_text   TEXT NOT NULL,
    created_at  REAL NOT NULL,
    deleted_at  REAL
);

CREATE TABLE IF NOT EXISTS quizzes (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT,
    questions   TEXT NOT NULL,
    profile     TEXT,
    result      TEXT,
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_docs_deleted ON documents(deleted_at);
CREATE INDEX IF NOT EXISTS idx_docs_created ON documents(created_at);
"""


def get_db() -> sqlite3.Connection:
    global _db
    if _db is not None:
        return _db
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _db = sqlite3.connect(str(settings.DB_PATH), check_same_thread=False)
    _db.row_factory = sqlite3.Row
    _db.execute("PRAGMA journal_mode=WAL")
    _db.execute("PRAGMA foreign_keys=ON")
    _db.executescript(SCHEMA)
    return _db


def close_db():
    global _db
    if _db is not None:
        _db.close()
        _db = None


# ── Document CRUD ──────────────────────────────────────────────────────

def save_document(doc: dict) -> None:
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO documents (id, name, pages, chunks, is_resume, profile, full_text, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            doc["id"], doc["name"], doc["pages"], doc["chunks"],
            int(doc["is_resume"]),
            json.dumps(doc.get("profile")) if doc.get("profile") else None,
            doc.get("text", ""),
            doc.get("created_at", time.time()),
        ),
    )
    db.commit()


def load_documents() -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM documents WHERE deleted_at IS NULL ORDER BY created_at DESC"
    ).fetchall()
    return [_row_to_doc(r) for r in rows]


def get_document(doc_id: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT * FROM documents WHERE id = ? AND deleted_at IS NULL", (doc_id,)
    ).fetchone()
    return _row_to_doc(row) if row else None


def delete_document(doc_id: str) -> bool:
    db = get_db()
    cur = db.execute(
        "UPDATE documents SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
        (time.time(), doc_id),
    )
    db.commit()
    return cur.rowcount > 0


def purge_expired() -> int:
    if settings.DOC_RETENTION_HOURS <= 0:
        return 0
    cutoff = time.time() - settings.DOC_RETENTION_HOURS * 3600
    db = get_db()
    cur = db.execute(
        "UPDATE documents SET deleted_at = ? WHERE created_at < ? AND deleted_at IS NULL",
        (time.time(), cutoff),
    )
    db.commit()
    return cur.rowcount


def _row_to_doc(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "pages": row["pages"],
        "chunks": row["chunks"],
        "is_resume": bool(row["is_resume"]),
        "profile": json.loads(row["profile"]) if row["profile"] else None,
        "text": row["full_text"],
        "created_at": row["created_at"],
    }


# ── Quiz CRUD ──────────────────────────────────────────────────────────

def save_quiz(quiz: dict) -> None:
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO quizzes (id, doc_id, questions, profile, result, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            quiz["id"],
            quiz.get("doc_id"),
            json.dumps(quiz["questions"]),
            json.dumps(quiz.get("profile")) if quiz.get("profile") else None,
            json.dumps(quiz.get("result")) if quiz.get("result") else None,
            quiz.get("created_at", time.time()),
        ),
    )
    db.commit()


def load_quiz(quiz_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "doc_id": row["doc_id"],
        "questions": json.loads(row["questions"]),
        "profile": json.loads(row["profile"]) if row["profile"] else None,
        "result": json.loads(row["result"]) if row["result"] else None,
        "created_at": row["created_at"],
    }


def save_quiz_result(quiz_id: str, result: dict) -> None:
    db = get_db()
    db.execute(
        "UPDATE quizzes SET result = ? WHERE id = ?",
        (json.dumps(result), quiz_id),
    )
    db.commit()
