from fastapi import APIRouter

from app.config import settings
from app.db import falkor
from app.models.schema import (
    Citation,
    OnboardingRecommendation,
    OnboardingResponse,
)
from app.services import gemini_service
from app.services.gemini_service import GeminiUnavailableError

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def _node(row: dict, key: str):
    value = row.get(key)
    return value.get("props", {}) if isinstance(value, dict) else {}


def _source_for(node_id: str) -> Citation | None:
    rows = falkor.read(
        "MATCH (n {id: $id})-[:FROM_MEETING]-(m:Meeting) "
        "RETURN n, m LIMIT 1",
        {"id": node_id},
    )
    if not rows:
        return None
    node_props = _node(rows[0], "n")
    meeting = _node(rows[0], "m")
    excerpt = node_props.get("source_excerpt")
    if not excerpt:
        return None
    return Citation(
        meeting_id=meeting.get("id", ""),
        meeting_title=meeting.get("title", "Source meeting"),
        meeting_date=meeting.get("meeting_date"),
        excerpt=excerpt,
        section=node_props.get("source_section"),
        entity_id=node_id,
        entity_type="Decision" if "summary" in node_props else "Task",
    )


@router.get("/{employee_id}", response_model=OnboardingResponse)
def onboarding_plan(employee_id: str):
    if employee_id == "sample":
        people = falkor.read(
            "MATCH (p:Person {is_new_hire: true}) RETURN p LIMIT 1"
        )
        person = _node(people[0], "p") if people else {}
        employee_id = person.get("id", "sample")
    else:
        people = falkor.read(
            "MATCH (p:Person {id: $id}) RETURN p LIMIT 1",
            {"id": employee_id},
        )
        person = _node(people[0], "p") if people else {}

    if not person:
        return OnboardingResponse(
            employee={
                "id": "sample",
                "name": "Sample new hire",
                "role": "New team member",
                "notice": "This is a sample profile because no matching employee context exists.",
            },
            is_sample_profile=True,
            recommendations=[],
            suggested_questions=[
                "Who owns the payments service?",
                "Why did the team choose Kafka?",
                "What should I review before my first sprint?",
            ],
        )

    person_id = person.get("id", employee_id)
    project_rows = falkor.read(
        "MATCH (p:Person {id: $id})-[:WORKS_ON|OWNS]-(project:Project) "
        "RETURN DISTINCT project LIMIT 12",
        {"id": person_id},
    )
    projects = [_node(row, "project") for row in project_rows]
    project_ids = [project.get("id") for project in projects if project.get("id")]
    task_rows = falkor.read(
        "MATCH (p:Person {id: $id})-[:OWNS]-(task:Task) RETURN DISTINCT task LIMIT 12",
        {"id": person_id},
    )
    tasks = [_node(row, "task") for row in task_rows]
    system_rows = falkor.read(
        "MATCH (p:Person {id: $id})-[:WORKS_ON|OWNS]-(project:Project)-[:USES]-(system:System) "
        "RETURN DISTINCT system LIMIT 12",
        {"id": person_id},
    )
    systems = [_node(row, "system") for row in system_rows]
    decisions = []
    if project_ids:
        decision_rows = falkor.read(
            "MATCH (decision:Decision)-[:AFFECTS_PROJECT]-(project:Project) "
            "WHERE project.id IN $ids RETURN DISTINCT decision LIMIT 12",
            {"ids": project_ids},
        )
        decisions = [_node(row, "decision") for row in decision_rows]

    recommendations = []
    candidate_ids: set[str] = set()
    for project in projects:
        recommendations.append(
            OnboardingRecommendation(
                title=f"Get oriented on {project.get('name', 'your project')}",
                description=project.get("description") or "Review the project relationships in company memory.",
                reason="This project is explicitly connected to your profile.",
                entity_id=project.get("id"),
            )
        )
        candidate_ids.add(project.get("id", ""))
    for system in systems:
        recommendations.append(
            OnboardingRecommendation(
                title=f"Learn {system.get('name', 'this system')}",
                description=system.get("description") or "Review how this system is used by your project.",
                reason="Your assigned project is connected to this system.",
                entity_id=system.get("id"),
            )
        )
        candidate_ids.add(system.get("id", ""))
    for decision in decisions:
        entity_id = decision.get("id", "")
        recommendations.append(
            OnboardingRecommendation(
                title=decision.get("summary", "Review an architecture decision"),
                description=decision.get("rationale", ""),
                reason="This decision affects your assigned project.",
                entity_id=entity_id,
                citation=_source_for(entity_id),
            )
        )
        candidate_ids.add(entity_id)
    for task in tasks:
        entity_id = task.get("id", "")
        recommendations.append(
            OnboardingRecommendation(
                title=task.get("description", "Review your open action item"),
                description=f"Status: {task.get('status', 'open')}",
                reason="This action item is explicitly assigned to you.",
                entity_id=entity_id,
                citation=_source_for(entity_id),
            )
        )
        candidate_ids.add(entity_id)

    recommendations = recommendations[:12]
    suggested_questions = [
        "Who can help me with the systems on my project?",
        "Which decisions affect my project?",
        "What action items are assigned to me?",
    ]
    ai_enhanced = False
    warning = None
    if settings.gemini_api_key and not settings.demo_mode and recommendations:
        context = {
            "employee": person,
            "recommendations": [item.model_dump(mode="json") for item in recommendations],
            "suggested_questions": suggested_questions,
        }
        try:
            generated = gemini_service.generate_onboarding_plan(context)
            supported = {
                item.entity_id: item for item in recommendations if item.entity_id
            }
            ordered = []
            for item in generated["recommendations"]:
                original = supported.get(item.get("entity_id"))
                if original:
                    ordered.append(
                        original.model_copy(
                            update={
                                "title": item["title"],
                                "description": item["description"],
                                "reason": item["reason"],
                            }
                        )
                    )
            if ordered:
                recommendations = ordered
                suggested_questions = generated["suggested_questions"] or suggested_questions
                ai_enhanced = True
        except GeminiUnavailableError as error:
            warning = str(error)

    return OnboardingResponse(
        employee=person,
        recommendations=recommendations,
        suggested_questions=suggested_questions,
        is_sample_profile=False,
        ai_enhanced=ai_enhanced,
        warning=warning,
    )
