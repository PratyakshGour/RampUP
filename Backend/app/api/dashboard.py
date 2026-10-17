from fastapi import APIRouter

from app.db import falkor

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _count(label: str) -> int:
    rows = falkor.read(f"MATCH (n:{label}) RETURN count(n) AS total")
    return int(rows[0]["total"]) if rows else 0


@router.get("/stats")
def dashboard_stats():
    meetings = falkor.read(
        "MATCH (m:Meeting) RETURN m ORDER BY m.meeting_date DESC LIMIT 5"
    )
    decisions = falkor.read(
        "MATCH (d:Decision) RETURN d ORDER BY d.created_at DESC LIMIT 5"
    )
    new_hires = falkor.read(
        "MATCH (p:Person {is_new_hire: true}) RETURN p.id AS id, p.name AS name LIMIT 1"
    )
    return {
        "meetings": _count("Meeting"),
        "people": _count("Person"),
        "projects": _count("Project"),
        "systems": _count("System"),
        "decisions": _count("Decision"),
        "open_tasks": len(
            falkor.read(
                "MATCH (task:Task) WHERE task.status IN ['open', 'blocked', 'in_progress'] "
                "RETURN task.id LIMIT 1000"
            )
        ),
        "recent_meetings": [
            row["m"].get("props", {}) for row in meetings
        ],
        "recent_decisions": [
            row["d"].get("props", {}) for row in decisions
        ],
        "sample_employee": new_hires[0] if new_hires else None,
    }
