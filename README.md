# DocMind

Ask questions about any PDF, Word or text document and get cited answers. Upload a resume to take a personalised, multiple-choice skills assessment, receive targeted guidance, and get a week-by-week learning roadmap for the role you want.

- **Plan and architecture**: [`docs/PLAN.md`](docs/PLAN.md)
- **Backend**: FastAPI, `backend/app/`
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

Optional: set `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` to get LLM-written answers. Without them, answers are extracted from the most relevant passages.

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
| GET | `/api/health` | Status |

## Layout

```
backend/app/     ingest, rag, resume, assessment, roadmap, knowledge, main
backend/tests/   pipeline and API tests
web/             index.html, styles.css, app.js, robots.txt, sitemap.xml
docs/PLAN.md     full plan
```
