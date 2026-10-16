"""Role-based learning roadmap with a week-by-week timetable.

Phases are weighted, so a shorter time window compresses every phase
proportionally. Gaps found in the assessment are pulled to the front.
"""
from .knowledge import TOPICS

ROLES = {
    "data_analyst": {
        "label": "Data Analyst",
        "summary": "Turn raw data into decisions with SQL, statistics and dashboards.",
        "phases": [
            {"name": "Foundations", "weight": 3, "focus": ["sql", "python"], "extras": ["Spreadsheet modelling", "Git basics"],
             "deliverable": "Write 30 SQL queries against a public dataset, including joins and window functions."},
            {"name": "Analysis & Statistics", "weight": 4, "focus": ["statistics", "data_visualization"], "extras": ["Cleaning messy data with pandas"],
             "deliverable": "Run an A/B test analysis and write a one-page findings memo."},
            {"name": "Portfolio & Interviews", "weight": 2, "focus": ["data_visualization"], "extras": ["STAR-format stories", "Case-study practice"],
             "deliverable": "Publish two dashboard case studies and complete five mock interviews."},
        ],
    },
    "ml_engineer": {
        "label": "Machine Learning Engineer",
        "summary": "Build, evaluate and ship models with solid Python and statistics.",
        "phases": [
            {"name": "Math & Python", "weight": 3, "focus": ["python", "statistics"], "extras": ["Linear algebra refresher"],
             "deliverable": "Implement linear regression from scratch using NumPy only."},
            {"name": "Modelling", "weight": 4, "focus": ["machine_learning", "sql"], "extras": ["Feature engineering", "Experiment tracking"],
             "deliverable": "Train and compare three models on one dataset with a written evaluation."},
            {"name": "Deployment", "weight": 3, "focus": ["cloud_devops", "system_design"], "extras": ["Model serving", "Monitoring for drift"],
             "deliverable": "Serve a model behind a versioned API in a container, with tests."},
        ],
    },
    "backend_engineer": {
        "label": "Backend Engineer",
        "summary": "Design reliable APIs, data stores and services that scale.",
        "phases": [
            {"name": "Core Language & Data", "weight": 3, "focus": ["python", "sql"], "extras": ["HTTP and REST fundamentals"],
             "deliverable": "Build a CRUD API with a relational database and migrations."},
            {"name": "Architecture", "weight": 4, "focus": ["system_design"], "extras": ["Queues and caching", "Auth and rate limiting"],
             "deliverable": "Write a design doc for a URL shortener covering scale, cache and failure modes."},
            {"name": "Ship & Operate", "weight": 3, "focus": ["cloud_devops"], "extras": ["Observability", "Load testing"],
             "deliverable": "Containerize the API, add CI, and deploy it with health checks and logs."},
        ],
    },
    "frontend_engineer": {
        "label": "Frontend Engineer",
        "summary": "Build fast, accessible interfaces with modern JavaScript.",
        "phases": [
            {"name": "JavaScript Core", "weight": 3, "focus": ["javascript"], "extras": ["HTML semantics", "CSS layout (Flexbox, Grid)"],
             "deliverable": "Build a static page with no frameworks that passes an accessibility audit."},
            {"name": "Framework & State", "weight": 4, "focus": ["javascript", "system_design"], "extras": ["Component design", "Testing with Playwright"],
             "deliverable": "Ship a small single-page app that fetches from a public API."},
            {"name": "Performance & Portfolio", "weight": 2, "focus": ["javascript"], "extras": ["Core Web Vitals", "SEO fundamentals"],
             "deliverable": "Reach a Lighthouse score above 90 on a portfolio site."},
        ],
    },
    "devops_engineer": {
        "label": "DevOps / Cloud Engineer",
        "summary": "Automate delivery, infrastructure and reliability in the cloud.",
        "phases": [
            {"name": "Linux & Scripting", "weight": 3, "focus": ["python", "cloud_devops"], "extras": ["Shell scripting", "Networking basics"],
             "deliverable": "Automate a server setup with a script, then repeat it in a container."},
            {"name": "Infrastructure as Code", "weight": 4, "focus": ["cloud_devops", "system_design"], "extras": ["Terraform modules", "Kubernetes basics"],
             "deliverable": "Provision a small cloud stack entirely with Terraform."},
            {"name": "Reliability", "weight": 3, "focus": ["system_design"], "extras": ["SLOs and alerting", "Incident response drills"],
             "deliverable": "Write a runbook and run a game-day exercise on your stack."},
        ],
    },
}


def _allocate_weeks(weights: list[int], total: int) -> list[int]:
    """Split total weeks across phases, giving each phase at least one week."""
    weight_sum = sum(weights)
    weeks = [max(1, round(total * w / weight_sum)) for w in weights]
    while sum(weeks) > total:
        weeks[weeks.index(max(weeks))] -= 1
    while sum(weeks) < total:
        weeks[weeks.index(min(weeks))] += 1
    return weeks


def build_roadmap(role_key: str, total_weeks: int = 12, hours_per_week: int = 10, gaps: list[str] | None = None) -> dict:
    role = ROLES[role_key]
    total_weeks = max(4, min(total_weeks, 26))
    gaps = [g for g in (gaps or []) if g in TOPICS]

    phases = role["phases"]
    week_counts = _allocate_weeks([p["weight"] for p in phases], total_weeks)

    timetable, phase_out, week_no = [], [], 1
    for phase, count in zip(phases, week_counts):
        focus = [TOPICS[t]["label"] for t in phase["focus"]]
        if gaps:
            priority = [TOPICS[g]["label"] for g in gaps if g in phase["focus"]]
            if priority:
                focus = [f"Shore up: {p}" for p in priority] + [f for f in focus if f not in priority]
        topics_text = focus + phase["extras"]
        phase_out.append({"name": phase["name"], "weeks": count, "start_week": week_no, "topics": topics_text, "deliverable": phase["deliverable"]})
        for i in range(count):
            is_last = i == count - 1
            timetable.append({
                "week": week_no,
                "phase": phase["name"],
                "topics": topics_text[i % len(topics_text)] if i < len(topics_text) else "Review and consolidate",
                "hours": hours_per_week,
                "milestone": phase["deliverable"] if is_last else None,
            })
            week_no += 1

    return {
        "role": role["label"],
        "summary": role["summary"],
        "total_weeks": total_weeks,
        "hours_per_week": hours_per_week,
        "total_hours": total_weeks * hours_per_week,
        "gaps_addressed": [TOPICS[g]["label"] for g in gaps],
        "phases": phase_out,
        "timetable": timetable,
    }


def role_options() -> list[dict]:
    return [{"key": key, "label": r["label"], "summary": r["summary"]} for key, r in ROLES.items()]
