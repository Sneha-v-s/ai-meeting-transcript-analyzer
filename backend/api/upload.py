# backend/api/upload.py
import logging
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException

from ..storage import create_meeting, get_upload_path, update_meeting
from ..workers import run_asr_job
from ..models.schemas import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> UploadResponse:
    """
    Receive an audio file, store it, and start background ASR using Whisper medium.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    original_name = file.filename
    meeting_id = create_meeting(original_name)

    logger.info("UPLOAD RECEIVED %s", original_name)

    # Save file to ../uploads/<id>_<filename>
    upload_path = get_upload_path(meeting_id, original_name)
    try:
        contents = await file.read()
        upload_path.write_bytes(contents)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error saving uploaded file: %s", exc)
        update_meeting(meeting_id, status="failed", error="Failed to save uploaded file")
        raise HTTPException(status_code=500, detail="Failed to save file")

    logger.info("File saved to %s", upload_path)

    # Start background ASR job
    logger.info("Starting processing for %s", meeting_id)
    background_tasks.add_task(run_asr_job, meeting_id, upload_path)
    update_meeting(meeting_id, status="queued", progress=20)

    return UploadResponse(
        meeting_id=meeting_id,
        filename=original_name,
        detail="Background processing started",
    )
