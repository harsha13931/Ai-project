"""Resume-based multiple-choice assessment with scoring and targeted guidance."""
import random
import uuid

from .knowledge import TOPICS

LEVELS = [
    (80, "Strong", "Your claimed skills hold up. Focus on depth and on showing results."),
    (50, "Developing", "The basics are there, but several answers were shaky. Close those gaps before interviews."),
    (0, "Needs foundation", "Fundamentals need work. Rebuild them before taking on advanced material."),
]


def build_quiz(profile: dict | None, num_questions: int = 0) -> dict:
    """Static fallback: pick from the knowledge bank when no LLM is available."""
    detected = set(profile["detected_topics"]) if profile else set()
    questions = []
    for topic, meta in TOPICS.items():
        pool = list(meta["questions"])
        random.shuffle(pool)
        picks = pool if topic in detected else pool[:1]
        for item in picks:
            questions.append({
                "id": uuid.uuid4().hex[:8],
                "topic": topic,
                "topic_label": meta["label"],
                "claimed": topic in detected,
                "q": item["q"],
                "options": item["options"],
                "_answer": item["answer"],
                "_explain": item["explain"],
            })
    random.shuffle(questions)
    if num_questions > 0:
        questions = questions[:num_questions]
    return {"id": uuid.uuid4().hex[:12], "questions": questions, "profile": profile}


def public_view(quiz: dict) -> dict:
    """What the browser may see: questions and options, never the answer key."""
    return {
        "id": quiz["id"],
        "total": len(quiz["questions"]),
        "questions": [
            {k: v for k, v in q.items() if not k.startswith("_")} for q in quiz["questions"]
        ],
    }


def score_quiz(quiz: dict, answers: dict[str, int]) -> dict:
    per_topic: dict[str, dict] = {}
    correct_total = 0
    review = []

    for q in quiz["questions"]:
        topic = per_topic.setdefault(q["topic"], {
            "topic": q["topic"], "label": q["topic_label"], "claimed": q["claimed"],
            "correct": 0, "total": 0,
        })
        chosen = answers.get(q["id"])
        is_correct = chosen == q["_answer"]
        topic["total"] += 1
        topic["correct"] += int(is_correct)
        correct_total += int(is_correct)
        review.append({
            "id": q["id"],
            "topic": q["topic_label"],
            "correct": is_correct,
            "your_answer": q["options"][chosen] if chosen is not None and 0 <= chosen < len(q["options"]) else None,
            "right_answer": q["options"][q["_answer"]],
            "explanation": q["_explain"],
        })

    topics = []
    for topic_key, stats in per_topic.items():
        pct = round(100 * stats["correct"] / stats["total"])
        static_topic = TOPICS.get(topic_key)
        topics.append({
            **stats,
            "percent": pct,
            "gap": pct < 100,
            "guidance": static_topic["guidance"] if static_topic and pct < 100 else
                        f"Review {stats['label']} fundamentals." if pct < 100 else None,
            "flag": "claimed but unverified" if stats["claimed"] and pct < 100 else None,
        })
    topics.sort(key=lambda t: t["percent"])

    overall = round(100 * correct_total / len(quiz["questions"]))
    level = next(name for threshold, name, _ in LEVELS if overall >= threshold)
    advice = next(text for threshold, _, text in LEVELS if overall >= threshold)

    return {
        "score": correct_total,
        "total": len(quiz["questions"]),
        "percent": overall,
        "level": level,
        "advice": advice,
        "topics": topics,
        "gaps": [t["topic"] for t in topics if t["gap"]],
        "review": review,
    }
