# backend/models/schemas.py
from typing import Optional
from pydantic import BaseModel


class MeetingStatus(BaseModel):
    id: str
    status: str
    progress: int
    error: Optional[str] = None


class UploadResponse(BaseModel):
    meeting_id: str
    filename: str
    detail: str
