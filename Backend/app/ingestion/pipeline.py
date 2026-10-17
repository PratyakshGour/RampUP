import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.ingestion.chunker import split_transcript
from app.models.schema import IngestionResult, MeetingMetadata
from app.services import gemini_service, graph_store
from app.services.gemini_service import GeminiUnavailableError


def _safe_filename(source_name: str) -> str:
    name = Path(source_name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not cleaned:
        cleaned = "transcript.txt"
    return cleaned[:180]


def _store_original(content: bytes, content_hash: str, source_name: str) -> str:
    settings.transcript_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{content_hash[:20]}_{_safe_filename(source_name)}"
    target = (settings.transcript_dir / stored_name).resolve()
    if settings.transcript_dir.resolve() not in target.parents:
        raise ValueError("Transcript path is outside the configured storage directory")
    if not target.exists():
        target.write_bytes(content)
    return stored_name


def _extraction_for(transcript: str, metadata: MeetingMetadata):
    if settings.demo_mode:
        return gemini_service.demo_extract_transcript(
            transcript,
            split_transcript(transcript, settings.transcript_chunk_chars),
        )
    return gemini_service.extract_chunks(
        transcript,
        metadata.model_dump(mode="json"),
        settings.transcript_chunk_chars,
    )


def ingest_transcript(content: bytes, metadata: MeetingMetadata) -> IngestionResult:
    if not content:
        raise ValueError("Transcript file is empty")
    try:
        transcript = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Transcript must be a UTF-8 text file") from error
    if len(transcript) > settings.max_transcript_chars:
        raise ValueError(
            f"Transcript exceeds the configured {settings.max_transcript_chars:,}-character limit"
        )

    content_hash = hashlib.sha256(content).hexdigest()
    meeting_id = graph_store.meeting_id_for(content_hash)
    stored_name = _store_original(content, content_hash, metadata.source_name)
    existing = graph_store.get_meeting_by_hash(content_hash)
    if existing:
        props = existing.get("props", {})
        meeting_id = props.get("id", meeting_id)
        if props.get("extraction_status") == "processed":
            return IngestionResult(
                meeting_id=meeting_id,
                title=props.get("title", metadata.title),
                status="duplicate",
                demo_mode=settings.demo_mode,
                summary={},
                message="This transcript was already processed; existing graph knowledge was reused.",
            )
        metadata = MeetingMetadata(
            title=props.get("title", metadata.title),
            meeting_date=props.get("meeting_date"),
            participants=json.loads(props.get("participants", "[]")),
            project_name=props.get("project_name"),
            source_name=props.get("source_name", metadata.source_name),
        )
    else:
        graph_store.upsert_node(
            "Meeting",
            meeting_id,
            {
                "title": metadata.title,
                "meeting_date": metadata.meeting_date,
                "participants": metadata.participants,
                "project_name": metadata.project_name,
                "source_name": metadata.source_name,
                "content_hash": content_hash,
                "storage_name": stored_name,
                "extraction_status": "pending",
            },
        )

    try:
        extraction = _extraction_for(transcript, metadata)
    except GeminiUnavailableError as error:
        graph_store.set_meeting_status(meeting_id, "failed", str(error))
        return IngestionResult(
            meeting_id=meeting_id,
            title=metadata.title,
            status="processing_failed",
            demo_mode=settings.demo_mode,
            summary={},
            message=str(error),
        )

    counts = graph_store.persist_extraction(meeting_id, metadata, extraction)
    graph_store.set_meeting_status(meeting_id, "processed")
    mode_message = (
        "Processed with deterministic demo extraction; no Gemini request was made."
        if settings.demo_mode
        else "Transcript processed and evidence added to company memory."
    )
    return IngestionResult(
        meeting_id=meeting_id,
        title=metadata.title,
        status="processed",
        demo_mode=settings.demo_mode,
        summary=counts,
        message=mode_message,
    )


def retry_meeting(meeting_id: str) -> IngestionResult:
    meeting = graph_store.get_meeting(meeting_id)
    if not meeting:
        raise KeyError("Meeting was not found")
    props: dict[str, Any] = meeting.get("props", {})
    storage_name = props.get("storage_name")
    if not storage_name:
        raise ValueError("Original transcript location is unavailable")
    path = (settings.transcript_dir / Path(storage_name).name).resolve()
    if settings.transcript_dir.resolve() not in path.parents:
        raise ValueError("Stored transcript path is invalid")
    if not path.is_file():
        raise FileNotFoundError("Original transcript could not be found")
    metadata = MeetingMetadata(
        title=props.get("title", "Untitled meeting"),
        meeting_date=props.get("meeting_date"),
        participants=json.loads(props.get("participants", "[]")),
        project_name=props.get("project_name"),
        source_name=props.get("source_name", path.name),
    )
    graph_store.set_meeting_status(meeting_id, "pending")
    return ingest_transcript(path.read_bytes(), metadata)
