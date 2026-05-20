# backend/api/meetings.py
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from ..storage import get_meeting
from ..models.schemas import MeetingStatus

router = APIRouter(tags=["meetings"])


@router.get("/meeting/{meeting_id}/status", response_model=MeetingStatus)
def get_meeting_status(meeting_id: str) -> MeetingStatus:
    data = get_meeting(meeting_id)
    if not data:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return MeetingStatus(
        id=data["id"],
        status=data["status"],
        progress=data["progress"],
        error=data.get("error"),
    )


@router.get("/meeting/{meeting_id}/transcript")
def get_meeting_transcript(meeting_id: str):
    data = get_meeting(meeting_id)
    if not data:
        raise HTTPException(status_code=404, detail="Meeting not found")

    path_str = data.get("transcript_path")
    if not path_str:
        raise HTTPException(status_code=404, detail="Transcript not ready")

    path = Path(path_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Transcript file missing")

    return FileResponse(path, media_type="application/json")
