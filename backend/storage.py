# backend/storage.py
import uuid
from pathlib import Path
from typing import Dict, Any

from .config import UPLOADS_DIR

# In‑memory progress + result store.
# For production, you would move this to Redis or a database.
_meetings: Dict[str, Dict[str, Any]] = {}


def get_upload_path(meeting_id: str, filename: str) -> Path:
    safe_name = filename.replace(" ", "_")
    return UPLOADS_DIR / f"{meeting_id}_{safe_name}"


def create_meeting(filename: str) -> str:
    meeting_id = uuid.uuid4().hex[:8]
    _meetings[meeting_id] = {
        "id": meeting_id,
        "filename": filename,
        "status": "pending",
        "progress": 0,
        "error": None,
        "transcript_path": None,
    }
    return meeting_id


def get_meeting(meeting_id: str) -> Dict[str, Any] | None:
    return _meetings.get(meeting_id)


def update_meeting(
    meeting_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    error: str | None = None,
    transcript_path: Path | None = None,
) -> None:
    data = _meetings.get(meeting_id)
    if not data:
        return
    if status is not None:
        data["status"] = status
    if progress is not None:
        data["progress"] = progress
    if error is not None:
        data["error"] = error
    if transcript_path is not None:
        data["transcript_path"] = str(transcript_path)


def get_upload_path(meeting_id: str, filename: str) -> Path:
    safe_name = filename.replace(" ", "_")
    return UPLOADS_DIR / f"{meeting_id}_{safe_name}"


def get_transcript_path(meeting_id: str) -> Path:
    return UPLOADS_DIR / f"{meeting_id}_transcript.json"
