import re
from typing import Any

from app import config
from app.db import falkor

STOP_WORDS = {
    "a", "an", "and", "are", "about", "can", "did", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "me", "of", "on", "our", "the", "their", "they",
    "to", "was", "we", "what", "when", "where", "which", "who", "why", "with",
    "would", "you", "your", "last", "week",
}

QUERY_TEMPLATES = {
    "decisions": """
        MATCH (n:Decision)
        WHERE any(term IN $terms WHERE
            toLower(coalesce(n.summary, '')) CONTAINS term OR
            toLower(coalesce(n.rationale, '')) CONTAINS term)
        OPTIONAL MATCH (n)-[:FROM_MEETING]-(m:Meeting)
        OPTIONAL MATCH (n)-[r]-(e)
        OPTIONAL MATCH (source:Meeting {id: r.source_meeting_id})
        RETURN n AS item, collect(DISTINCT m) AS meetings,
            collect(DISTINCT e) AS related,
            collect(DISTINCT {type: type(r), excerpt: r.source_excerpt,
                meeting_id: source.id, meeting_title: source.title,
                meeting_date: source.meeting_date}) AS relationships
        LIMIT $limit
    """,
    "people": """
        MATCH (n:Person)-[r]-(e)
        WHERE type(r) IN ['EXPERT_IN', 'WORKS_ON', 'OWNS', 'ATTENDED', 'MENTIONED_IN'] AND
            any(term IN $terms WHERE
            toLower(coalesce(n.name, '')) CONTAINS term OR
            toLower(coalesce(n.role, '')) CONTAINS term OR
            toLower(coalesce(e.name, e.description, e.title, '')) CONTAINS term)
        OPTIONAL MATCH (source:Meeting {id: r.source_meeting_id})
        RETURN n AS item, collect(DISTINCT source) AS meetings,
            collect(DISTINCT e) AS related,
            collect(DISTINCT {type: type(r), excerpt: r.source_excerpt,
                meeting_id: source.id, meeting_title: source.title,
                meeting_date: source.meeting_date}) AS relationships
        LIMIT $limit
    """,
    "projects": """
        MATCH (n:Project)
        WHERE any(term IN $terms WHERE
            toLower(coalesce(n.name, '')) CONTAINS term OR
            toLower(coalesce(n.description, '')) CONTAINS term)
        OPTIONAL MATCH (n)-[r]-(e)
        OPTIONAL MATCH (n)-[:CONTAINS|ABOUT_PROJECT|AFFECTS_PROJECT]-(m:Meeting)
        OPTIONAL MATCH (source:Meeting {id: r.source_meeting_id})
        RETURN n AS item, collect(DISTINCT m) AS meetings,
            collect(DISTINCT e) AS related,
            collect(DISTINCT {type: type(r), excerpt: r.source_excerpt,
                meeting_id: source.id, meeting_title: source.title,
                meeting_date: source.meeting_date}) AS relationships
        LIMIT $limit
    """,
    "tasks": """
        MATCH (n:Task)
        WHERE any(term IN $terms WHERE
            toLower(coalesce(n.description, '')) CONTAINS term OR
            toLower(coalesce(n.status, '')) CONTAINS term OR
            toLower(coalesce(n.owner_name, '')) CONTAINS term)
        OPTIONAL MATCH (n)-[:FROM_MEETING]-(m:Meeting)
        OPTIONAL MATCH (n)-[r]-(e)
        RETURN n AS item, collect(DISTINCT m) AS meetings,
            collect(DISTINCT e) AS related, collect(DISTINCT type(r)) AS relationships
        LIMIT $limit
    """,
    "meetings": """
        MATCH (n:Meeting)
        WHERE any(term IN $terms WHERE
            toLower(coalesce(n.title, '')) CONTAINS term OR
            toLower(coalesce(n.project_name, '')) CONTAINS term)
        OPTIONAL MATCH (n)-[r]-(e)
        RETURN n AS item, [n] AS meetings,
            collect(DISTINCT e) AS related,
            collect(DISTINCT {type: type(r), excerpt: r.source_excerpt}) AS relationships
        LIMIT $limit
    """,
    "knowledge": """
        MATCH (n)
        WHERE any(term IN $terms WHERE
            toLower(coalesce(n.content, n.summary, n.description, '')) CONTAINS term)
        OPTIONAL MATCH (n)-[:FROM_MEETING]-(m:Meeting)
        OPTIONAL MATCH (n)-[r]-(e)
        RETURN n AS item, collect(DISTINCT m) AS meetings,
            collect(DISTINCT e) AS related,
            collect(DISTINCT type(r)) AS relationships
        LIMIT $limit
    """,
}

QUERY_TEMPLATES["systems"] = """
    MATCH (n:System)
    WHERE any(term IN $terms WHERE
        toLower(coalesce(n.name, '')) CONTAINS term OR
        toLower(coalesce(n.description, '')) CONTAINS term)
    OPTIONAL MATCH (n)-[r]-(e)
    OPTIONAL MATCH (n)-[:USES|AFFECTS_SYSTEM|ABOUT_SYSTEM]-(m:Meeting)
    OPTIONAL MATCH (source:Meeting {id: r.source_meeting_id})
    RETURN n AS item, collect(DISTINCT m) AS meetings,
        collect(DISTINCT e) AS related,
        collect(DISTINCT {type: type(r), excerpt: r.source_excerpt,
            meeting_id: source.id, meeting_title: source.title,
            meeting_date: source.meeting_date}) AS relationships
    LIMIT $limit
"""

QUERY_TEMPLATES["facts"] = """
    MATCH (n:Fact)
    WHERE any(term IN $terms WHERE
        toLower(coalesce(n.content, '')) CONTAINS term)
    OPTIONAL MATCH (n)-[:FROM_MEETING]-(m:Meeting)
    OPTIONAL MATCH (n)-[r]-(e)
    RETURN n AS item, collect(DISTINCT m) AS meetings,
        collect(DISTINCT e) AS related, collect(DISTINCT type(r)) AS relationships
    LIMIT $limit
"""

QUERY_TEMPLATES["task_knowledge"] = """
    MATCH (n:Task)
    WHERE any(term IN $terms WHERE
        toLower(coalesce(n.description, '')) CONTAINS term)
    OPTIONAL MATCH (n)-[:FROM_MEETING]-(m:Meeting)
    OPTIONAL MATCH (n)-[r]-(e)
    RETURN n AS item, collect(DISTINCT m) AS meetings,
        collect(DISTINCT e) AS related, collect(DISTINCT type(r)) AS relationships
    LIMIT $limit
"""

HISTORICAL_DECISIONS_QUERY = """
    MATCH (new:Decision)-[r:SUPERSEDES]->(old:Decision)
    WHERE size($terms) = 0 OR any(term IN $terms WHERE
        toLower(coalesce(new.summary, '')) CONTAINS term OR
        toLower(coalesce(new.rationale, '')) CONTAINS term OR
        toLower(coalesce(old.summary, '')) CONTAINS term OR
        toLower(coalesce(old.rationale, '')) CONTAINS term)
    UNWIND [new, old] AS decision
    OPTIONAL MATCH (decision)-[:FROM_MEETING]-(m:Meeting)
    WITH new, old, decision, collect(DISTINCT m) AS meetings
    RETURN decision AS item, meetings,
        CASE WHEN decision.id = new.id THEN [old] ELSE [new] END AS related,
        [{type: 'SUPERSEDES', description:
            new.summary + ' supersedes ' + old.summary}] AS relationships
    LIMIT $limit
"""


def classify_question(question: str) -> str:
    text = question.lower()
    if any(word in text for word in (
        "decision", "decid", "why", "choose", "chose", "architecture", "rationale",
        "changed", "original", "latest", "supersed", "historical",
    )):
        return "decisions"
    if any(word in text for word in ("who", "expert", "mentor", "owner", "help")):
        return "people"
    if any(word in text for word in ("task", "action item", "blocker", "todo", "next step")):
        return "tasks"
    if any(word in text for word in ("meeting", "sync", "discussed", "last week", "what changed")):
        return "meetings"
    if any(word in text for word in ("project", "system", "service", "depend", "connected", "uses")):
        return "projects"
    return "knowledge"


def _terms(question: str) -> list[str]:
    tokens = [
        token for token in re.findall(r"[a-z0-9][a-z0-9+#.-]{1,}", question.lower())
        if token not in STOP_WORDS
    ]
    expansions = []
    for token in tokens:
        expansions.append(token)
        if token.endswith("s") and len(token) > 4:
            expansions.append(token[:-1])
        if token == "auth":
            expansions.append("authentication")
            expansions.extend(("oauth2", "identity gateway"))
        if token == "authentication":
            expansions.extend(("oauth2", "identity gateway"))
        if token == "payments":
            expansions.append("payment")
    return list(dict.fromkeys(expansions))[:12]


def retrieve_evidence(question: str, limit: int | None = None) -> dict[str, Any]:
    category = classify_question(question)
    terms = _terms(question)
    if not terms:
        return {"category": category, "items": [], "related_entities": []}
    max_items = limit or config.settings.max_evidence_items
    historical = any(
        term in question.lower()
        for term in ("original", "latest", "changed", "supersed", "historical", "before")
    )
    if historical and category == "decisions":
        topic_terms = [
            term
            for term in terms
            if term
            not in {
                "original",
                "latest",
                "changed",
                "historical",
                "supersed",
                "before",
                "decision",
                "decisions",
                "between",
            }
        ]
        query_groups = [
            falkor.read(
                HISTORICAL_DECISIONS_QUERY,
                {"terms": topic_terms, "limit": max_items},
            )
        ]
    elif category in {"projects", "knowledge"}:
        names = ("projects", "systems") if category == "projects" else (
            "facts",
            "decisions",
            "task_knowledge",
            "projects",
            "systems",
        )
        query_groups = [
            falkor.read(QUERY_TEMPLATES[name], {"terms": terms, "limit": max_items})
            for name in names
        ]
    else:
        query_groups = [
            falkor.read(
                QUERY_TEMPLATES[category],
                {"terms": terms, "limit": max_items},
            )
        ]
    rows = [row for group in query_groups for row in group]
    evidence = []
    related_entities: dict[str, dict[str, str]] = {}
    for row in rows:
        node = row.get("item") or {}
        props = node.get("props", {})
        label = node.get("label", "Knowledge")
        meetings = [value for value in row.get("meetings", []) if isinstance(value, dict)]
        related = [value for value in row.get("related", []) if isinstance(value, dict)]
        source_meeting = meetings[0].get("props", {}) if meetings else {}
        relation_evidence = [
            value for value in row.get("relationships", [])
            if isinstance(value, dict) and value.get("excerpt")
        ]
        sourced_relation = next(
            (
                value
                for value in relation_evidence
                if value.get("meeting_id")
            ),
            None,
        )
        if sourced_relation:
            source_meeting = {
                "id": sourced_relation.get("meeting_id"),
                "title": sourced_relation.get("meeting_title"),
                "meeting_date": sourced_relation.get("meeting_date"),
            }
        excerpt = (
            (sourced_relation.get("excerpt") if sourced_relation else None)
            or props.get("source_excerpt")
            or props.get("rationale")
            or props.get("content")
            or props.get("description")
            or (relation_evidence[0]["excerpt"] if relation_evidence else "")
            or ""
        )
        content = (
            props.get("summary")
            or props.get("content")
            or props.get("description")
            or props.get("name")
            or props.get("title")
            or props.get("task")
        )
        if not content and label == "Task":
            content = props.get("description")
        evidence.append(
            {
                "id": props.get("id", node.get("id", "")),
                "type": label,
                "content": content or "",
                "excerpt": excerpt,
                "section": props.get("source_section"),
                "timestamp_start": props.get("timestamp_start"),
                "timestamp_end": props.get("timestamp_end"),
                "meeting_id": source_meeting.get("id", ""),
                "meeting_title": source_meeting.get("title", "Source meeting"),
                "meeting_date": source_meeting.get("meeting_date"),
                "relationships": [
                    (
                        value.get("description")
                        or value.get("type", "")
                        if isinstance(value, dict)
                        else value
                    )
                    for value in row.get("relationships", [])
                ],
            }
        )
        for entity in related:
            entity_props = entity.get("props", {})
            entity_id = entity_props.get("id", entity.get("id", ""))
            name = (
                entity_props.get("name")
                or entity_props.get("summary")
                or entity_props.get("description")
                or entity_props.get("title")
            )
            if entity_id and name:
                related_entities[entity_id] = {
                    "id": entity_id,
                    "label": entity.get("label", "Entity"),
                    "name": str(name),
                }
    evidence = [item for item in evidence if item["content"] or item["excerpt"]]
    return {
        "category": category,
        "items": evidence[: config.settings.max_evidence_items],
        "related_entities": list(related_entities.values())[:20],
    }


def evidence_strength(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "none"
    source_count = len({item.get("meeting_id") for item in evidence if item.get("meeting_id")})
    excerpt_count = sum(bool(item.get("excerpt")) for item in evidence)
    if source_count >= 2 and excerpt_count >= 2:
        return "strong"
    if excerpt_count >= 2 or source_count >= 2:
        return "moderate"
    return "limited"
