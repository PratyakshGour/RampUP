from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.db import falkor
from app.ingestion.pipeline import ingest_transcript, retry_meeting
from app.models.schema import IngestionResult, MeetingMetadata
from app.services import graph_store

router = APIRouter(prefix="/api/meetings", tags=["meetings"])
ALLOWED_EXTENSIONS = {".txt", ".md"}


def _public_meeting(node: dict) -> dict:
    props = dict(node.get("props", {}))
    props.pop("storage_name", None)
    props.pop("content_hash", None)
    participants = props.get("participants", "[]")
    if isinstance(participants, str):
        import json

        props["participants"] = json.loads(participants)
    return props


@router.post("/upload", response_model=IngestionResult, status_code=status.HTTP_202_ACCEPTED)
async def upload_meeting(
    title: str = Form(min_length=1, max_length=200),
    meeting_date: date | None = Form(default=None),
    participants: str = Form(default=""),
    project_name: str | None = Form(default=None, max_length=160),
    file: UploadFile = File(...),
):
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only .txt and .md transcripts are supported.")
    content = await file.read(settings.max_transcript_bytes + 1)
    if len(content) > settings.max_transcript_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Transcript exceeds the {settings.max_transcript_bytes:,}-byte upload limit.",
        )
    participant_names = [name.strip() for name in participants.split(",") if name.strip()]
    try:
        metadata = MeetingMetadata(
            title=title.strip(),
            meeting_date=meeting_date,
            participants=participant_names,
            project_name=project_name.strip() if project_name else None,
            source_name=filename,
        )
        return ingest_transcript(content, metadata)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/{meeting_id}/process", response_model=IngestionResult, status_code=202)
def process_saved_meeting(meeting_id: str):
    try:
        return retry_meeting(meeting_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("")
def list_meetings(limit: int = 50):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    rows = falkor.read(
        "MATCH (m:Meeting) RETURN m ORDER BY m.meeting_date DESC LIMIT $limit",
        {"limit": limit},
    )
    return [_public_meeting(row["m"]) for row in rows]


@router.get("/{meeting_id}")
def get_meeting(meeting_id: str):
    meeting = graph_store.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting was not found")
    return _public_meeting(meeting)


@router.get("/{meeting_id}/evidence")
def meeting_evidence(meeting_id: str):
    meeting = graph_store.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting was not found")
    rows = falkor.read(
        "MATCH (n)-[:FROM_MEETING]->(m:Meeting {id: $id}) "
        "RETURN n ORDER BY labels(n)[0], n.id",
        {"id": meeting_id},
    )
    return {
        "meeting": _public_meeting(meeting),
        "evidence": [
            {
                "id": row["n"].get("props", {}).get("id", row["n"].get("id")),
                "type": row["n"].get("label"),
                **row["n"].get("props", {}),
            }
            for row in rows
        ],
    }
