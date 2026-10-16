"""Prompt templates for every stage of the pipeline.

Each template is a LangChain ``ChatPromptTemplate`` so it plugs straight
into a chain.  Import the one you need — no raw strings scattered across
the codebase.
"""
from langchain_core.prompts import ChatPromptTemplate

# ── 1. RAG question-answering ──────────────────────────────────────────

RAG_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a precise document Q&A assistant.\n"
        "Rules:\n"
        "- Answer using ONLY the numbered context passages below.\n"
        "- Cite every claim with its source number, e.g. [1].\n"
        "- If the context does not contain the answer, reply: "
        '"I could not find that in the uploaded documents."\n'
        "- Be concise, accurate, and well-structured.",
    ),
    (
        "human",
        "Context:\n{context}\n\nQuestion: {question}",
    ),
])

# ── 2. Resume analysis ────────────────────────────────────────────────

RESUME_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an expert technical recruiter and resume analyst.\n"
        "Given a resume, extract a structured JSON profile with these keys:\n"
        '  "name": string or null,\n'
        '  "years_experience": integer or null,\n'
        '  "education": [strings],\n'
        '  "experience_lines": [strings — one line per role],\n'
        '  "detected_topics": [topic keys from the allowed list],\n'
        '  "claimed_skills": [human-readable skill labels],\n'
        '  "summary": one-paragraph professional summary.\n\n'
        "Allowed topic keys and their labels:\n"
        "  python → Python, sql → SQL & Databases,\n"
        "  statistics → Statistics, machine_learning → Machine Learning,\n"
        "  javascript → JavaScript & Frontend,\n"
        "  system_design → System Design,\n"
        "  cloud_devops → Cloud & DevOps,\n"
        "  data_visualization → Data Visualization.\n\n"
        "Return ONLY valid JSON, no markdown fences.",
    ),
    (
        "human",
        "Resume text:\n{resume_text}",
    ),
])

# ── 3. Quiz question generation ───────────────────────────────────────

QUIZ_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an assessment designer for technical skills.\n"
        "Given a candidate profile, generate targeted multiple-choice questions.\n\n"
        "Rules:\n"
        "- For each *claimed* skill: generate 2 questions (intermediate to advanced).\n"
        "- For each *unclaimed* skill from the allowed list: generate 1 basic question.\n"
        "- Each question has exactly 4 options, one correct.\n"
        "- Return a JSON array of objects with keys:\n"
        '  "topic" (topic key), "topic_label", "claimed" (bool),\n'
        '  "q" (question text), "options" [4 strings],\n'
        '  "answer" (0-based index of correct option),\n'
        '  "explain" (one-sentence explanation).\n\n'
        "Return ONLY valid JSON, no markdown fences.",
    ),
    (
        "human",
        "Candidate profile:\n{profile}\n\n"
        "Allowed topics: {topics}",
    ),
])

# ── 4. Score analysis & guidance ──────────────────────────────────────

GUIDANCE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a career coach specialising in tech skills.\n"
        "Given a quiz result with per-topic scores, provide:\n"
        "1. A one-paragraph overall assessment.\n"
        "2. For each topic where the candidate scored below 100 %:\n"
        "   - What to study first.\n"
        "   - One practical exercise.\n"
        "   - One resource recommendation.\n"
        "Be encouraging but honest. Keep each topic guidance to 2–3 sentences.",
    ),
    (
        "human",
        "Quiz results:\n{results}",
    ),
])

# ── 5. Roadmap generation ─────────────────────────────────────────────

ROADMAP_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a learning-path architect.\n"
        "Given a target role, total weeks, hours per week, and identified gaps,\n"
        "produce a structured JSON roadmap with keys:\n"
        '  "phases": [{{"name", "weeks", "start_week", "topics": [strings],\n'
        '              "deliverable": string}}],\n'
        '  "timetable": [{{"week", "phase", "topics" (string),\n'
        '                  "hours", "milestone": string|null}}].\n\n'
        "Rules:\n"
        "- Gaps from the assessment go into the EARLIEST matching phase.\n"
        "- Each phase ends with a concrete deliverable.\n"
        "- The timetable has exactly one row per week.\n"
        "Return ONLY valid JSON, no markdown fences.",
    ),
    (
        "human",
        "Role: {role}\nWeeks: {weeks}\nHours per week: {hours}\n"
        "Gaps to address first: {gaps}\n"
        "Role description: {role_description}",
    ),
])
