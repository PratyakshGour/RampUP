import hashlib
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api import graph as graph_api
from app.config import settings
from app.db import falkor
from app.ingestion.pipeline import ingest_transcript
from app.main import app
from app.models.schema import (
    DecisionExtraction,
    FactExtraction,
    MeetingMetadata,
    PersonExtraction,
    ProjectExtraction,
    SystemExtraction,
    TranscriptExtraction,
)
from app.services import gemini_service, graph_store, retrieval

client = TestClient(app)


def test_health_reports_database_status():
    with patch.object(falkor, "ping", return_value=False):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"


def test_upload_rejects_unsupported_file():
    response = client.post(
        "/api/meetings/upload",
        data={"title": "Unsafe upload"},
        files={"file": ("notes.pdf", b"not a transcript", "application/pdf")},
    )
    assert response.status_code == 415


def test_upload_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(settings, "max_transcript_bytes", 4)
    response = client.post(
        "/api/meetings/upload",
        data={"title": "Large upload"},
        files={"file": ("notes.txt", b"12345", "text/plain")},
    )
    assert response.status_code == 413


def test_extraction_validation_requires_evidence():
    try:
        TranscriptExtraction(
            decisions=[
                {
                    "summary": "Use Kafka",
                    "status": "confirmed",
                    "source_excerpt": "",
                }
            ]
        )
    except ValueError:
        return
    raise AssertionError("an unsupported decision must not validate")


def test_relationship_extraction_requires_supporting_excerpt():
    try:
        PersonExtraction(name="Sam", expertise_in=["OAuth2"])
    except ValueError:
        return
    raise AssertionError("expertise must be evidence-backed")


def test_entity_names_normalize_to_stable_ids():
    assert graph_store.normalize_name("Ríya Sharma") == "riya-sharma"
    assert graph_store.stable_id("person", "Riya Sharma") == graph_store.stable_id(
        "person", "RIYA  SHARMA"
    )


def test_node_upsert_uses_write_query():
    with patch.object(graph_store, "ensure_indexes"), patch.object(
        falkor, "run", return_value=[]
    ) as write, patch.object(falkor, "read") as read:
        graph_store.upsert_node("Person", "person:riya", {"name": "Riya"})
    assert write.call_args.args[0].startswith("MERGE (n:Person")
    read.assert_not_called()


def test_graph_type_filter_keeps_adjacent_nodes_without_duplicate_ids():
    person = {
        "_type": "node",
        "id": "person:riya",
        "label": "Person",
        "props": {"id": "person:riya", "name": "Riya"},
    }
    project = {
        "_type": "node",
        "id": "project:payments",
        "label": "Project",
        "props": {"id": "project:payments", "name": "Payments"},
    }
    with patch.object(
        falkor,
        "read",
        side_effect=[
            [{"n": person}],
            [
                {
                    "a": person,
                    "b": project,
                    "source": "person:riya",
                    "target": "project:payments",
                    "relationship": "WORKS_ON",
                    "properties": {},
                }
            ],
        ],
    ):
        result = graph_api.get_graph(node_type="Person", focus=None, limit=200)
    assert [node["id"] for node in result["nodes"]] == [
        "person:riya",
        "project:payments",
    ]
    assert result["edges"][0]["source"] == "person:riya"
    assert result["edges"][0]["target"] == "project:payments"


def test_duplicate_ingestion_reuses_existing_extraction(tmp_path, monkeypatch):
    content = b"Riya and Priya discussed the payments project."
    digest = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(settings, "transcript_dir", tmp_path)
    monkeypatch.setattr(
        graph_store,
        "get_meeting_by_hash",
        lambda _: {
            "props": {
                "id": graph_store.meeting_id_for(digest),
                "title": "Existing meeting",
                "extraction_status": "processed",
            }
        },
    )
    with patch.object(gemini_service, "extract_transcript") as extraction:
        result = ingest_transcript(
            content,
            MeetingMetadata(title="Changed title", source_name="notes.txt"),
        )
    assert result.status == "duplicate"
    assert result.title == "Existing meeting"
    extraction.assert_not_called()
    assert list(tmp_path.iterdir())


def test_structured_gemini_extraction_is_validated(monkeypatch):
    response = {
        "people": [],
        "projects": [],
        "systems": [],
        "decisions": [],
        "tasks": [],
        "facts": [
            {
                "content": "Payments use Kafka.",
                "source_excerpt": "Payments use Kafka.",
                "source_section": "Section 1",
            }
        ],
    }
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    with patch.object(gemini_service, "_request", return_value=json.dumps(response)):
        extracted = gemini_service.extract_transcript(
            "Payments use Kafka.",
            {"title": "Test"},
            "Section 1",
        )
    assert extracted.facts[0].content == "Payments use Kafka."
    assert extracted.facts[0].source_section == "Section 1"


def test_graph_persistence_is_deterministic_and_links_source():
    extraction = TranscriptExtraction(
        decisions=[
            DecisionExtraction(
                summary="Use Kafka",
                status="confirmed",
                rationale="Supports replay.",
                source_excerpt="We confirmed Kafka for event replay.",
            )
        ],
        facts=[
            FactExtraction(
                content="Payment events use Kafka.",
                systems=["Kafka"],
                source_excerpt="Payment events use Kafka.",
            )
        ],
    )
    metadata = MeetingMetadata(title="Sync", source_name="sync.md")
    with patch.object(graph_store, "upsert_node"), patch.object(graph_store, "link") as link, patch.object(
        falkor, "read", return_value=[]
    ):
        first = graph_store.persist_extraction("meeting:abc", metadata, extraction)
        second = graph_store.persist_extraction("meeting:abc", metadata, extraction)
    assert first == second == {
        "people": 0,
        "projects": 0,
        "systems": 0,
        "decisions": 1,
        "tasks": 0,
        "facts": 1,
    }
    produced_call = (
        "meeting:abc",
        graph_store.stable_id("decision", "meeting:abc-Use Kafka"),
        "PRODUCED",
    )
    assert sum(call.args == produced_call for call in link.call_args_list) == 2


def test_system_persistence_keeps_source_meeting_and_excerpt():
    excerpt = "The Identity Gateway validates OAuth2 access tokens."
    extraction = TranscriptExtraction(
        systems=[
            SystemExtraction(
                name="Identity Gateway",
                description="Validates access tokens.",
                source_excerpt=excerpt,
            )
        ]
    )
    with patch.object(graph_store, "upsert_node") as upsert, patch.object(
        graph_store, "link"
    ) as link:
        graph_store.persist_extraction(
            "meeting:auth",
            MeetingMetadata(title="Authentication handoff"),
            extraction,
        )
    system_id = graph_store.stable_id("system", "Identity Gateway")
    upsert.assert_any_call(
        "System",
        system_id,
        {
            "name": "Identity Gateway",
            "description": "Validates access tokens.",
            "source_excerpt": excerpt,
        },
    )
    link.assert_any_call(
        system_id,
        "meeting:auth",
        "MENTIONED_IN",
        {"source_excerpt": excerpt, "source_meeting_id": "meeting:auth"},
    )


def test_historical_decision_is_linked_only_when_supersedes_is_explicit():
    extraction = TranscriptExtraction(
        decisions=[
            DecisionExtraction(
                summary="Use the identity gateway",
                status="confirmed",
                supersedes="Validate tokens in the API",
                source_excerpt="The gateway now validates tokens.",
            )
        ]
    )
    with patch.object(graph_store, "upsert_node"), patch.object(graph_store, "link") as link, patch.object(
        falkor, "read", return_value=[{"id": "decision:old"}]
    ):
        graph_store.persist_extraction(
            "meeting:new",
            MeetingMetadata(title="Auth sync"),
            extraction,
        )
    link.assert_any_call(
        graph_store.stable_id("decision", "meeting:new-Use the identity gateway"),
        "decision:old",
        "SUPERSEDES",
    )


def test_decision_retrieval_keeps_meeting_citation():
    node = {
        "_type": "node",
        "id": "decision:kafka",
        "label": "Decision",
        "props": {
            "id": "decision:kafka",
            "summary": "Use Kafka for asynchronous payment events",
            "rationale": "Kafka supports event replay.",
            "source_excerpt": "We chose Kafka because it supports event replay.",
            "source_section": "Section 2",
        },
    }
    meeting = {
        "_type": "node",
        "id": "meeting:sync",
        "label": "Meeting",
        "props": {
            "id": "meeting:sync",
            "title": "Payments architecture sync",
            "meeting_date": "2026-10-03",
        },
    }
    with patch.object(
        falkor,
        "read",
        return_value=[
            {
                "item": node,
                "meetings": [meeting],
                "related": [],
                "relationships": [],
            }
        ],
    ):
        result = retrieval.retrieve_evidence("Why did we choose Kafka?")
    assert result["category"] == "decisions"
    assert result["items"][0]["meeting_id"] == "meeting:sync"
    assert result["items"][0]["excerpt"].startswith("We chose Kafka")


def test_historical_decision_retrieval_traverses_supersession_chain():
    decision = {
        "_type": "node",
        "id": "decision:gateway",
        "label": "Decision",
        "props": {
            "id": "decision:gateway",
            "summary": "Use the identity gateway",
            "source_excerpt": "We replaced API token validation with the gateway.",
            "source_section": "Section 3",
        },
    }
    meeting = {
        "_type": "node",
        "id": "meeting:auth",
        "label": "Meeting",
        "props": {
            "id": "meeting:auth",
            "title": "Authentication design",
            "meeting_date": "2026-10-03",
        },
    }
    with patch.object(
        falkor,
        "read",
        return_value=[
            {
                "item": decision,
                "meetings": [meeting],
                "related": [],
                "relationships": [
                    {
                        "type": "SUPERSEDES",
                        "description": "Use the identity gateway supersedes Validate tokens in the API",
                    }
                ],
            }
        ],
    ) as read:
        result = retrieval.retrieve_evidence(
            "What changed between the original and latest decision?"
        )
    assert result["category"] == "decisions"
    assert result["items"][0]["meeting_id"] == "meeting:auth"
    assert "SUPERSEDES" in read.call_args.args[0]
    assert read.call_args.args[1]["terms"] == []
    assert result["items"][0]["relationships"] == [
        "Use the identity gateway supersedes Validate tokens in the API"
    ]


def test_expert_retrieval_uses_relationship_evidence():
    person = {
        "_type": "node",
        "id": "person:arjun",
        "label": "Person",
        "props": {"id": "person:arjun", "name": "Arjun Mehta", "role": "Platform engineer"},
    }
    system = {
        "_type": "node",
        "id": "system:oauth",
        "label": "System",
        "props": {"id": "system:oauth", "name": "OAuth2"},
    }
    source = {
        "_type": "node",
        "id": "meeting:auth",
        "label": "Meeting",
        "props": {"id": "meeting:auth", "title": "Authentication handoff"},
    }
    with patch.object(
        falkor,
        "read",
        return_value=[
            {
                "item": person,
                "meetings": [source],
                "related": [system],
                "relationships": [{"type": "EXPERT_IN", "excerpt": "Arjun is the OAuth2 expert."}],
            }
        ],
    ):
        result = retrieval.retrieve_evidence("Who can help with OAuth2?")
    assert result["category"] == "people"
    assert result["items"][0]["excerpt"] == "Arjun is the OAuth2 expert."
    assert result["items"][0]["meeting_title"] == "Authentication handoff"


def test_relationship_citation_uses_excerpt_from_its_exact_source_meeting():
    node = {
        "_type": "node",
        "id": "system:oauth",
        "label": "System",
        "props": {
            "id": "system:oauth",
            "name": "OAuth2",
            "source_excerpt": "A later meeting mentions the same system.",
        },
    }
    with patch.object(
        falkor,
        "read",
        return_value=[
            {
                "item": node,
                "meetings": [],
                "related": [],
                "relationships": [
                    {
                        "type": "MENTIONED_IN",
                        "excerpt": "This meeting defines the OAuth2 boundary.",
                        "meeting_id": "meeting:auth",
                        "meeting_title": "Authentication handoff",
                        "meeting_date": "2026-10-06",
                    }
                ],
            }
        ],
    ):
        result = retrieval.retrieve_evidence("Tell me about OAuth2")
    item = result["items"][0]
    assert item["meeting_id"] == "meeting:auth"
    assert item["excerpt"] == "This meeting defines the OAuth2 boundary."


def test_cross_meeting_retrieval_keeps_distinct_sources():
    def node(node_id, title, excerpt):
        return {
            "_type": "node",
            "id": node_id,
            "label": "Fact",
            "props": {
                "id": node_id,
                "content": "Payments use Kafka.",
                "source_excerpt": excerpt,
            },
        }

    rows = []
    for index in range(2):
        rows.append(
            {
                "item": node(f"fact:{index}", "Payment fact", f"Source excerpt {index}"),
                "meetings": [
                    {
                        "_type": "node",
                        "id": f"meeting:{index}",
                        "label": "Meeting",
                        "props": {
                            "id": f"meeting:{index}",
                            "title": f"Meeting {index}",
                            "meeting_date": f"2026-10-0{index + 1}",
                        },
                    }
                ],
                "related": [],
                "relationships": [],
            }
        )
    with patch.object(falkor, "read", return_value=rows):
        result = retrieval.retrieve_evidence("How are payments using Kafka?")
    assert {item["meeting_id"] for item in result["items"]} == {"meeting:0", "meeting:1"}


def test_empty_retrieval_returns_insufficient_evidence():
    with patch.object(falkor, "read", return_value=[]):
        result = retrieval.retrieve_evidence("What is the office Wi-Fi password?")
    assert result["items"] == []
    assert retrieval.evidence_strength(result["items"]) == "none"


def test_chat_response_does_not_call_gemini_without_citations(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "gemini_api_key", "unused")
    with patch.object(retrieval, "retrieve_evidence", return_value={
        "category": "knowledge",
        "items": [],
        "related_entities": [],
    }), patch.object(chat_api, "_persist_message"), patch.object(
        gemini_service, "answer_with_evidence"
    ) as answer:
        response = client.post("/api/chat", json={"question": "Tell me an unsupported thing"})
    assert response.status_code == 200
    assert response.json()["evidence_strength"] == "none"
    assert response.json()["citations"] == []
    answer.assert_not_called()
