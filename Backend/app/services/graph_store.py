import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Any

from app.db import falkor
from app.models.schema import MeetingMetadata, TranscriptExtraction

NODE_LABELS = {
    "Person",
    "Meeting",
    "Project",
    "System",
    "Decision",
    "Task",
    "Fact",
    "ChatSession",
    "ChatMessage",
}
RELATION_TYPES = {
    "ATTENDED",
    "PRODUCED",
    "CONTAINS",
    "FROM_MEETING",
    "WORKS_ON",
    "OWNS",
    "EXPERT_IN",
    "USES",
    "AFFECTS_PROJECT",
    "AFFECTS_SYSTEM",
    "SUPERSEDES",
    "ABOUT_PERSON",
    "ABOUT_PROJECT",
    "ABOUT_SYSTEM",
    "MENTIONED_IN",
    "HAS_MESSAGE",
}
INDEXES = (
    ("Person", "id"),
    ("Meeting", "id"),
    ("Meeting", "content_hash"),
    ("Project", "id"),
    ("System", "id"),
    ("Decision", "id"),
    ("Task", "id"),
    ("Fact", "id"),
)
_indexes_ready = False


def normalize_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def stable_id(kind: str, value: str) -> str:
    normalized = normalize_name(value)
    suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{suffix}"


def _properties(properties: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in properties.items():
        if value is None:
            continue
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        elif isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=True)
        result[key] = value
    return result


def ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return

    # Initialize the graph before querying its indexes.
    falkor.run("CREATE (n:OnboardOSBootstrap)")

    rows = falkor.read("CALL db.indexes()")
    existing = set()
    for row in rows:
        label = row.get("label")
        properties = row.get("properties", [])
        if isinstance(properties, str):
            properties = [properties]
        existing.update((label, prop) for prop in properties)

    for label, property_name in INDEXES:
        if (label, property_name) not in existing:
            falkor.run(
                f"CREATE INDEX FOR (n:{label}) ON (n.{property_name})"
            )

    _indexes_ready = True


def upsert_node(label: str, node_id: str, properties: dict[str, Any]) -> dict[str, Any]:
    if label not in NODE_LABELS:
        raise ValueError(f"Unsupported node label: {label}")
    ensure_indexes()
    props = _properties({"id": node_id, **properties})
    rows = falkor.run(
        f"MERGE (n:{label} {{id: $id}}) SET n += $props RETURN n",
        {"id": node_id, "props": props},
    )
    return rows[0]["n"] if rows else {"id": node_id, "label": label, "props": props}


def link(
    source_id: str,
    target_id: str,
    relationship: str,
    properties: dict[str, Any] | None = None,
) -> None:
    if relationship not in RELATION_TYPES:
        raise ValueError(f"Unsupported relationship: {relationship}")
    falkor.run(
        f"MATCH (a {{id: $source_id}}), (b {{id: $target_id}}) "
        f"MERGE (a)-[r:{relationship}]->(b) SET r += $props",
        {
            "source_id": source_id,
            "target_id": target_id,
            "props": _properties(properties or {}),
        },
    )


def meeting_id_for(content_hash: str) -> str:
    return f"meeting:{content_hash[:24]}"


def get_meeting_by_hash(content_hash: str) -> dict[str, Any] | None:
    rows = falkor.read(
        "MATCH (m:Meeting {content_hash: $content_hash}) RETURN m LIMIT 1",
        {"content_hash": content_hash},
    )
    return rows[0]["m"] if rows else None


def get_meeting(meeting_id: str) -> dict[str, Any] | None:
    rows = falkor.read(
        "MATCH (m:Meeting {id: $id}) RETURN m LIMIT 1",
        {"id": meeting_id},
    )
    return rows[0]["m"] if rows else None


def set_meeting_status(meeting_id: str, status: str, message: str = "") -> None:
    falkor.run(
        "MATCH (m:Meeting {id: $id}) SET m.extraction_status = $status, "
        "m.processing_message = $message",
        {"id": meeting_id, "status": status, "message": message[:500]},
    )


def persist_extraction(
    meeting_id: str,
    metadata: MeetingMetadata,
    extraction: TranscriptExtraction,
) -> dict[str, int]:
    meeting_props = {
        "title": metadata.title,
        "meeting_date": metadata.meeting_date,
        "source_name": metadata.source_name,
        "extraction_status": "processed",
    }
    if metadata.project_name:
        meeting_props["project_name"] = metadata.project_name
    upsert_node("Meeting", meeting_id, meeting_props)

    people: dict[str, str] = {}
    projects: dict[str, str] = {}
    systems: dict[str, str] = {}

    for item in extraction.people:
        person_id = stable_id("person", item.name)
        people[normalize_name(item.name)] = person_id
        upsert_node(
            "Person",
            person_id,
            {
                "name": item.name,
                "role": item.role,
                "team": item.team,
                "source_excerpt": item.source_excerpt,
                "is_new_hire": item.new_hire,
            },
        )
        link(
            person_id,
            meeting_id,
            "MENTIONED_IN",
            {
                "source_excerpt": item.source_excerpt,
                "source_meeting_id": meeting_id,
            },
        )
        for project_name in item.works_on:
            project_id = stable_id("project", project_name)
            projects[normalize_name(project_name)] = project_id
            upsert_node("Project", project_id, {"name": project_name})
            link(
                person_id,
                project_id,
                "WORKS_ON",
                {"source_excerpt": item.source_excerpt, "source_meeting_id": meeting_id},
            )
        for system_name in item.expertise_in:
            system_id = stable_id("system", system_name)
            systems[normalize_name(system_name)] = system_id
            upsert_node("System", system_id, {"name": system_name})
            link(
                person_id,
                system_id,
                "EXPERT_IN",
                {"source_excerpt": item.source_excerpt, "source_meeting_id": meeting_id},
            )

    for name in metadata.participants:
        person_id = people.get(normalize_name(name)) or stable_id("person", name)
        people[normalize_name(name)] = person_id
        upsert_node("Person", person_id, {"name": name})
        link(person_id, meeting_id, "ATTENDED", {"source_meeting_id": meeting_id})
        link(person_id, meeting_id, "MENTIONED_IN", {"source_meeting_id": meeting_id})
    for person in extraction.people:
        if person.attended:
            link(
                people[normalize_name(person.name)],
                meeting_id,
                "ATTENDED",
                {
                    "source_excerpt": person.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )

    for item in extraction.systems:
        system_id = stable_id("system", item.name)
        systems[normalize_name(item.name)] = system_id
        upsert_node(
            "System",
            system_id,
            {
                "name": item.name,
                "description": item.description,
                "source_excerpt": item.source_excerpt,
            },
        )
        link(
            system_id,
            meeting_id,
            "MENTIONED_IN",
            {
                "source_excerpt": item.source_excerpt,
                "source_meeting_id": meeting_id,
            },
        )

    for item in extraction.projects:
        project_id = stable_id("project", item.name)
        projects[normalize_name(item.name)] = project_id
        upsert_node("Project", project_id, {"name": item.name, "description": item.description})
        link(meeting_id, project_id, "CONTAINS")
        link(
            project_id,
            meeting_id,
            "MENTIONED_IN",
            {
                "source_excerpt": item.source_excerpt,
                "source_meeting_id": meeting_id,
            },
        )
        for system_name in item.systems:
            system_id = systems.get(normalize_name(system_name)) or stable_id("system", system_name)
            systems[normalize_name(system_name)] = system_id
            upsert_node("System", system_id, {"name": system_name})
            link(
                project_id,
                system_id,
                "USES",
                {
                    "source_excerpt": item.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )
        if item.owner:
            owner_id = people.get(normalize_name(item.owner)) or stable_id("person", item.owner)
            people[normalize_name(item.owner)] = owner_id
            upsert_node("Person", owner_id, {"name": item.owner})
            link(
                owner_id,
                project_id,
                "OWNS",
                {"source_excerpt": item.source_excerpt, "source_meeting_id": meeting_id},
            )
        for person in extraction.people:
            if any(normalize_name(project) == normalize_name(item.name) for project in person.works_on):
                link(
                    people[normalize_name(person.name)],
                    project_id,
                    "WORKS_ON",
                    {
                        "source_excerpt": person.source_excerpt,
                        "source_meeting_id": meeting_id,
                    },
                )

    if metadata.project_name:
        project_id = projects.get(normalize_name(metadata.project_name)) or stable_id(
            "project", metadata.project_name
        )
        projects[normalize_name(metadata.project_name)] = project_id
        upsert_node("Project", project_id, {"name": metadata.project_name})
        link(meeting_id, project_id, "CONTAINS")

    counts = {
        "people": len(extraction.people),
        "projects": len(extraction.projects) + int(bool(metadata.project_name)),
        "systems": len(extraction.systems),
        "decisions": len(extraction.decisions),
        "tasks": len(extraction.tasks),
        "facts": len(extraction.facts),
    }

    for item in extraction.decisions:
        decision_id = stable_id("decision", f"{meeting_id}-{item.summary}")
        upsert_node(
            "Decision",
            decision_id,
            {
                "summary": item.summary,
                "status": item.status,
                "rationale": item.rationale,
                "source_excerpt": item.source_excerpt,
                "source_section": item.source_section,
                "timestamp_start": item.timestamp_start,
                "timestamp_end": item.timestamp_end,
                "created_at": metadata.meeting_date,
            },
        )
        link(meeting_id, decision_id, "PRODUCED")
        link(
            decision_id,
            meeting_id,
            "FROM_MEETING",
            {
                "source_excerpt": item.source_excerpt,
                "source_meeting_id": meeting_id,
            },
        )
        if item.project:
            project_id = projects.get(normalize_name(item.project)) or stable_id("project", item.project)
            projects[normalize_name(item.project)] = project_id
            upsert_node("Project", project_id, {"name": item.project})
            link(
                decision_id,
                project_id,
                "AFFECTS_PROJECT",
                {
                    "source_excerpt": item.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )
        for system_name in item.systems:
            system_id = systems.get(normalize_name(system_name)) or stable_id("system", system_name)
            systems[normalize_name(system_name)] = system_id
            upsert_node("System", system_id, {"name": system_name})
            link(
                decision_id,
                system_id,
                "AFFECTS_SYSTEM",
                {
                    "source_excerpt": item.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )
        if item.supersedes:
            superseded_id = stable_id("decision", f"{meeting_id}-{item.supersedes}")
            rows = falkor.read(
                "MATCH (d:Decision) WHERE d.id = $id OR toLower(d.summary) = toLower($summary) "
                "RETURN d.id AS id LIMIT 1",
                {"id": item.supersedes, "summary": item.supersedes},
            )
            if rows:
                link(decision_id, rows[0]["id"], "SUPERSEDES")
            elif superseded_id == decision_id:
                raise ValueError("A decision cannot supersede itself")

    for index, item in enumerate(extraction.tasks):
        task_id = stable_id("task", f"{meeting_id}-{item.description}")
        upsert_node(
            "Task",
            task_id,
            {
                "description": item.description,
                "status": item.status,
                "due_date": item.due_date,
                "owner_name": item.owner,
                "source_excerpt": item.source_excerpt,
                "source_section": item.source_section,
            },
        )
        link(meeting_id, task_id, "CONTAINS")
        link(
            task_id,
            meeting_id,
            "FROM_MEETING",
            {
                "source_excerpt": item.source_excerpt,
                "source_meeting_id": meeting_id,
            },
        )
        if item.owner:
            owner_id = people.get(normalize_name(item.owner)) or stable_id("person", item.owner)
            people[normalize_name(item.owner)] = owner_id
            upsert_node("Person", owner_id, {"name": item.owner})
            link(
                owner_id,
                task_id,
                "OWNS",
                {
                    "source_excerpt": item.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )
        if item.project:
            project_id = projects.get(normalize_name(item.project)) or stable_id("project", item.project)
            projects[normalize_name(item.project)] = project_id
            upsert_node("Project", project_id, {"name": item.project})
            link(
                task_id,
                project_id,
                "AFFECTS_PROJECT",
                {
                    "source_excerpt": item.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )

    for index, item in enumerate(extraction.facts):
        fact_id = stable_id(
            "fact",
            f"{meeting_id}-{item.source_section or index}-{item.content}",
        )
        upsert_node(
            "Fact",
            fact_id,
            {
                "content": item.content,
                "category": item.category,
                "source_excerpt": item.source_excerpt,
                "source_section": item.source_section,
                "timestamp_start": item.timestamp_start,
                "timestamp_end": item.timestamp_end,
            },
        )
        link(meeting_id, fact_id, "CONTAINS")
        link(
            fact_id,
            meeting_id,
            "FROM_MEETING",
            {
                "source_excerpt": item.source_excerpt,
                "source_meeting_id": meeting_id,
            },
        )
        for name in item.people:
            person_id = people.get(normalize_name(name)) or stable_id("person", name)
            people[normalize_name(name)] = person_id
            upsert_node("Person", person_id, {"name": name})
            link(
                fact_id,
                person_id,
                "ABOUT_PERSON",
                {
                    "source_excerpt": item.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )
        for name in item.projects:
            project_id = projects.get(normalize_name(name)) or stable_id("project", name)
            projects[normalize_name(name)] = project_id
            upsert_node("Project", project_id, {"name": name})
            link(
                fact_id,
                project_id,
                "ABOUT_PROJECT",
                {
                    "source_excerpt": item.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )
        for name in item.systems:
            system_id = systems.get(normalize_name(name)) or stable_id("system", name)
            systems[normalize_name(name)] = system_id
            upsert_node("System", system_id, {"name": name})
            link(
                fact_id,
                system_id,
                "ABOUT_SYSTEM",
                {
                    "source_excerpt": item.source_excerpt,
                    "source_meeting_id": meeting_id,
                },
            )

    for entity_id in set((*people.values(), *projects.values(), *systems.values())):
        link(
            meeting_id,
            entity_id,
            "CONTAINS",
            {"source_meeting_id": meeting_id},
        )
    return counts
