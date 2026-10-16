"""Resume detection and profile extraction.

Rule-based extraction runs always (no API key needed).  When the LLM is
configured, ``graph.py`` enriches the profile with deeper analysis.
"""
import re

from .knowledge import TOPICS

SECTION_HINTS = ["experience", "education", "skills", "projects", "certifications", "summary", "objective"]
DEGREE = re.compile(r"\b(b\.?\s?tech|b\.?\s?e\.?|b\.?sc|bachelor|m\.?\s?tech|m\.?sc|master|ph\.?d|mba|diploma)\b", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.\w+")
YEARS = re.compile(r"(\d{1,2})\+?\s*(?:years|yrs)", re.I)
YEAR_RANGE = re.compile(r"\b(19|20)\d{2}\b")


def looks_like_resume(text: str) -> bool:
    lower = text.lower()
    hits = sum(1 for hint in SECTION_HINTS if re.search(rf"\b{hint}\b", lower))
    return hits >= 3 or (hits >= 2 and bool(EMAIL.search(text)))


def _topic_present(lower_text: str, keyword: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lower_text) is not None


def build_profile(text: str) -> dict:
    lower = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    name = next(
        (line for line in lines[:3] if len(line.split()) <= 4 and not re.search(r"[\d@|]", line)),
        None,
    )
    years = max((int(m) for m in YEARS.findall(text)), default=None)
    education = [line for line in lines if DEGREE.search(line)][:4]
    experience = [line for line in lines if YEAR_RANGE.search(line)][:8]
    detected = [
        topic
        for topic, meta in TOPICS.items()
        if any(_topic_present(lower, kw) for kw in meta["keywords"])
    ]

    return {
        "name": name,
        "years_experience": years,
        "education": education,
        "experience_lines": experience,
        "detected_topics": detected,
        "claimed_skills": [TOPICS[t]["label"] for t in detected],
    }
