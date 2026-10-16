# DocMind

Ask questions about any PDF, Word or text document and get cited answers. Upload a resume to take a personalised, multiple-choice skills assessment, receive targeted guidance, and get a week-by-week learning roadmap for the role you want.

**Powered by:** LangChain, LangGraph, HuggingFace Embeddings, FAISS, FastAPI

- **Plan and architecture**: [`docs/PLAN.md`](docs/PLAN.md)
- **Backend**: FastAPI + LangChain + LangGraph, `backend/app/`
- **Website**: static HTML, CSS and JS, `web/`

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q tests
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Configuration (one place)

All settings are in **`backend/app/config.py`**, read from environment variables:

```bash
# Required for LLM-powered features (optional — app works without them):
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-sonnet-4-20250514"

# Embeddings (free, works out of the box):
export EMBEDDING_MODEL="all-MiniLM-L6-v2"   # default, no API key needed
export EMBEDDING_DEVICE="cpu"                 # or "cuda" for GPU

# RAG tuning (optional):
export CHUNK_SIZE=900
export CHUNK_OVERLAP=150
export RETRIEVAL_K=4
export SCORE_THRESHOLD=0.05
```

To switch API keys or models, change the env var — no code changes needed.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/documents` | Upload PDF, DOCX, TXT or MD (max 10 MB) |
| GET | `/api/documents` | List loaded documents |
| POST | `/api/ask` | `{question, doc_id?}` → answer with sources |
| POST | `/api/quiz` | Create a resume-based assessment |
| POST | `/api/quiz/{id}/submit` | `{answers: {questionId: optionIndex}}` → score and guidance |
| GET | `/api/roles` | Available role tracks |
| POST | `/api/roadmap` | `{role, weeks, hours_per_week, quiz_id?}` → phases and timetable |
| GET | `/api/health` | Status, embeddings model, LLM status |

## Tech stack

| Component | Technology |
|---|---|
| Orchestration | **LangGraph** — state-machine workflows |
| Chains & Prompts | **LangChain** — prompt templates per stage |
| Embeddings | **HuggingFace** `all-MiniLM-L6-v2` — free, local |
| Vector store | **FAISS** — fast similarity search |
| LLM | **Anthropic Claude** via LangChain (optional) |
| API | **FastAPI** |
| Web | Vanilla HTML/CSS/JS |

## Layout

```
backend/app/
  config.py         ← all settings & API keys (one place)
  prompts.py        ← LangChain prompt templates for each stage
  chains.py         ← LangChain chain factories
  graph.py          ← LangGraph workflows
  ingest.py         ← extract, chunk, embed
  rag.py            ← FAISS vector store + retrieval
  resume.py         ← resume detection
  assessment.py     ← MCQ scoring
  roadmap.py        ← learning roadmaps
  knowledge.py      ← question bank
  main.py           ← FastAPI endpoints
backend/tests/      ← pipeline and API tests
web/                ← index.html, styles.css, app.js
docs/PLAN.md        ← full architecture plan
```
