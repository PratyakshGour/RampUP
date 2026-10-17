import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.db import falkor
from app.models.schema import (
    ChatRequest,
    ChatResponse,
    Citation,
    RelatedEntity,
)
from app.services import gemini_service, graph_store, retrieval
from app.services.gemini_service import GeminiUnavailableError

router = APIRouter(prefix="/api/chat", tags=["company memory"])


def _citations(items: list[dict]) -> list[Citation]:
    citations = []
    seen = set()
    for item in items:
        meeting_id = item.get("meeting_id")
        excerpt = item.get("excerpt")
        if not meeting_id or not excerpt:
            continue
        key = (meeting_id, item.get("id"))
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                meeting_id=meeting_id,
                meeting_title=item.get("meeting_title") or "Source meeting",
                meeting_date=item.get("meeting_date"),
                excerpt=excerpt,
                section=item.get("section"),
                entity_id=item.get("id", ""),
                entity_type=item.get("type", "Fact"),
                timestamp_start=item.get("timestamp_start"),
                timestamp_end=item.get("timestamp_end"),
            )
        )
    return citations


def _persist_message(session_id: str, role: str, content: str, extras: dict | None = None):
    session_node_id = f"chat-session:{session_id}"
    graph_store.upsert_node(
        "ChatSession",
        session_node_id,
        {"session_id": session_id, "updated_at": datetime.now(timezone.utc)},
    )
    message_id = f"chat-message:{uuid.uuid4()}"
    graph_store.upsert_node(
        "ChatMessage",
        message_id,
        {
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc),
            "metadata": extras or {},
        },
    )
    graph_store.link(session_node_id, message_id, "HAS_MESSAGE")


@router.post("", response_model=ChatResponse)
def ask_company_memory(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    try:
        session_id = str(uuid.UUID(session_id))
    except ValueError as error:
        raise HTTPException(status_code=422, detail="session_id must be a UUID") from error

    result = retrieval.retrieve_evidence(request.question)
    evidence = result["items"]
    citations = _citations(evidence)
    strength = retrieval.evidence_strength(evidence)
    provider = "evidence_only"
    warning = None

    if not citations:
        answer = "Company memory does not establish an answer with source evidence yet."
    elif settings.demo_mode:
        provider = "demo"
        answer = " ".join(
            item["excerpt"] for item in evidence if item.get("excerpt")
        )[:2200]
        answer = f"From the synthetic demo meeting evidence: {answer}"
    elif settings.gemini_api_key:
        try:
            answer = gemini_service.answer_with_evidence(request.question, evidence)
            provider = "gemini"
        except GeminiUnavailableError as error:
            provider = "grounded_fallback"
            warning = str(error)
            answer = " ".join(item["excerpt"] for item in evidence if item.get("excerpt"))[:2200]
            answer = f"Here is the retrieved source evidence: {answer}"
    else:
        provider = "grounded_fallback"
        warning = "Gemini is not configured. Showing only retrieved transcript evidence."
        answer = " ".join(item["excerpt"] for item in evidence if item.get("excerpt"))[:2200]
        answer = f"Here is the retrieved source evidence: {answer}"

    response = ChatResponse(
        answer=answer,
        category=result["category"],
        evidence_strength=strength,
        citations=citations,
        related_entities=[
            RelatedEntity(**entity) for entity in result["related_entities"]
        ],
        session_id=session_id,
        answer_provider=provider,
        warning=warning,
    )
    _persist_message(session_id, "user", request.question)
    _persist_message(session_id, "assistant", response.answer, response.model_dump(mode="json"))
    return response


@router.get("/history")
def chat_history(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    if not session_id:
        return {"session_id": None, "messages": []}
    try:
        session_id = str(uuid.UUID(session_id))
    except ValueError as error:
        raise HTTPException(status_code=422, detail="session_id must be a UUID") from error
    rows = falkor.read(
        "MATCH (m:ChatMessage {session_id: $session_id}) "
        "RETURN m ORDER BY m.created_at DESC LIMIT $limit",
        {"session_id": session_id, "limit": limit},
    )
    messages = [
        row["m"].get("props", {})
        for row in reversed(rows)
    ]
    for message in messages:
        value = message.get("metadata", "{}")
        message["metadata"] = json.loads(value) if isinstance(value, str) else value
    return {"session_id": session_id, "messages": messages}


@router.post("/new")
def new_chat():
    return {"session_id": str(uuid.uuid4())}
