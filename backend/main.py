from typing import Dict, Any
import os
import sys
import uuid
import json
from datetime import datetime
from pathlib import Path

import requests  # for calling Ollama HTTP API
from openai import OpenAI
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Import config first
from config import WHISPER_MODEL, UPLOADS_DIR, BASE_DIR

# OpenAI client (used for Whisper, if you still use OpenAI for ASR)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# FastAPI app setup
app = FastAPI(title="AI Meeting Transcript Analyzer")

# Use absolute paths based on BASE_DIR
static_dir = BASE_DIR / "frontend" / "static"
templates_dir = BASE_DIR / "frontend" / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Import workers after app created
from workers.asr import transcribe_audio, save_transcript

# =========================
# Pydantic models
# =========================

class MeetingResponse(BaseModel):
    meeting_id: str
    filename: str
    status: str
    created_at: str


class ActionItem(BaseModel):
    task: str
    owner: str | None = None


class ActionItemsResponse(BaseModel):
    items: list[ActionItem]


class SummaryResponse(BaseModel):
    summary: str

# =========================
# Helper functions
# =========================

def classify_transcript(text: str) -> str:
    """
    Simple heuristic to guess the content type from the transcript text.
    Returns:
        "meeting"  - likely a meeting / work discussion
        "song"     - likely song lyrics
        "generic"  - fallback for anything else.
    """
    lower = text.lower()

    meeting_keywords = [
        "meeting", "minutes", "agenda", "action item",
        "project", "deadline", "sprint", "task", "client", "stakeholder"
    ]
    song_keywords = [
        "chorus", "verse", "bridge", "lyrics", "guitar",
        "melody", "chorus:", "hook", "refrain"
    ]

    if any(k in lower for k in meeting_keywords):
        return "meeting"
    if any(k in lower for k in song_keywords):
        return "song"

    return "generic"


def make_summary_prompt(transcript_type: str, full_text: str) -> str:
    """
    Build a natural-language prompt for the local LLM (via Ollama),
    depending on the content type.
    """
    base = full_text[:4000]

    if transcript_type == "meeting":
        # Structured, pointwise meeting notes.
        return (
            "You are an assistant that writes clear, structured meeting notes.\n"
            "You will receive a raw transcript of a real meeting.\n"
            "\n"
            "Your goal is to produce notes that someone can understand at a glance.\n"
            "Follow this EXACT structure:\n"
            "\n"
            "1) Meeting Overview:\n"
            "- 1–2 short bullet points describing what the meeting was about.\n"
            "\n"
            "2) Key Discussion Points:\n"
            "- 4–8 bullet points summarizing the main topics discussed.\n"
            "- Each bullet should be one concise sentence.\n"
            "\n"
            "3) Decisions Made:\n"
            "- 2–6 bullet points listing any decisions, approvals, or agreements.\n"
            "- If no clear decisions were made, write: \"- No explicit decisions recorded.\"\n"
            "\n"
            "4) Next Steps / Action Items:\n"
            "- 3–8 bullet points.\n"
            "- Each bullet should follow this pattern if possible: \"[Owner]: [Action] [Optional deadline]\".\n"
            "- If the owner is not mentioned, write: \"[Unassigned]: [Action]\".\n"
            "\n"
            "Important guidelines:\n"
            "- Write everything in simple, direct English.\n"
            "- Do NOT add extra commentary or analysis; stick to what is in the transcript.\n"
            "- Do NOT invent people or tasks that are not clearly implied.\n"
            "- Use bullet points and numbered sections as described; no long paragraphs.\n"
            "\n"
            "Now here is the meeting transcript:\n"
            f"{base}"
        )

    elif transcript_type == "song":
        # Song-style summary: focus on themes, emotions, images, tone shifts.
        return (
            "You are summarizing a song's lyrics.\n"
            "Write a thoughtful paragraph (4–5 sentences) that captures:\n"
            "- the main themes and emotions,\n"
            "- a a few vivid images or memories mentioned,\n"
            "- the emotional conflict or journey,\n"
            "- and how the mood or tone shifts across the song.\n"
            "Write in a natural, reviewer-like style, not as a template.\n"
            "Do not quote large chunks of the lyrics; paraphrase in your own words.\n\n"
            f"Lyrics or transcript:\n{base}"
        )

    else:
        # Generic text summary: just a good, human-like paragraph.
        return (
            "You are summarizing a piece of text.\n"
            "Write a clear, human-sounding paragraph (4–7 sentences) that captures the main ideas,\n"
            "important details, and overall tone of the text.\n"
            "Avoid bullet points and rigid templates; write it like a short article summary.\n"
            "Do not invent details that are not in the text.\n\n"
            f"Text:\n{base}"
        )


def run_ollama(prompt: str, model: str = "phi3:mini") -> str:
    """
    Call a local Ollama model to generate text.
    """
    url = "http://localhost:11434/api/generate"

    response = requests.post(
        url,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )
    response.raise_for_status()
    data = response.json()
    return data.get("response", "").strip()


def extract_action_items(transcript: str) -> list[ActionItem]:
    """
    Extract action items from transcript using intelligent keyword matching.
    """
    items: list[ActionItem] = []

    action_keywords = [
        "will do", "will send", "will provide", "will create", "will fix", "will update",
        "need to", "need to do", "needs to", "should", "should do",
        "must do", "must", "please", "please do",
        "to do", "todo", "task:", "action:", "deliverable:",
        "assigned to", "assigned", "responsible for",
        "by ", "deadline", "due date", "finish", "complete",
        "prepare", "organize", "schedule", "meeting", "call"
    ]

    lines = transcript.split('\n')

    for line in lines:
        text = line.strip()
        if not text or len(text) < 15:
            continue

        lower = text.lower()

        has_action = any(k in lower for k in action_keywords)
        if not has_action:
            continue

        if len(text) > 300:
            continue

        if any(pattern in lower for pattern in ["singing", "song", "music", "verse", "chorus", "bridge"]):
            continue

        owner = None
        task = text

        # Try to extract owner: "Alice: will finish the report"
        if ":" in text and len(text.split(":")[0].split()) <= 3:
            parts = text.split(":", 1)
            maybe_owner = parts[0].strip()
            rest = parts[1].strip()

            if len(maybe_owner) < 30 and len(maybe_owner.split()) <= 3:
                owner = maybe_owner
                task = rest

        if task and any(k in task.lower() for k in action_keywords):
            items.append(ActionItem(task=task[:200], owner=owner))

    # Remove duplicates
    seen = set()
    unique_items = []
    for item in items:
        key = (item.task.lower()[:50], item.owner.lower() if item.owner else "")
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items[:10]

# =========================
# Routes
# =========================

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Serve the main HTML frontend.
    """
    index_path = BASE_DIR / "frontend" / "templates" / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/health")
async def health():
    return {"status": "OK", "message": "AI Meeting Analyzer is running!"}


@app.post("/upload", response_model=MeetingResponse)
async def upload(file: UploadFile = File(...)):
    """
    Upload endpoint: accepts audio/video, saves file, and runs the processing pipeline.
    Behavior: same as before (blocking processing).
    """
    if not (file.content_type and (file.content_type.startswith("audio/") or file.content_type.startswith("video/"))):
        return {"error": "Only audio/video files allowed"}

    meeting_id = str(uuid.uuid4())[:8]
    filename = file.filename
    file_path = UPLOADS_DIR / f"{meeting_id}_{filename}"

    print(f"📤 UPLOAD RECEIVED: {filename}")

    content = await file.read()
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    print(f"💾 File saved to: {file_path}")

    print("⚡ Starting processing NOW...")
    process_meeting(meeting_id, str(file_path))
    print("✅ Processing complete!")

    return MeetingResponse(
        meeting_id=meeting_id,
        filename=filename,
        status="complete",
        created_at=datetime.now().isoformat()
    )


@app.get("/api/meeting/{meeting_id}")
async def get_meeting_api(meeting_id: str):
    """
    Get meeting results as JSON (original behavior).
    """
    transcript_path = UPLOADS_DIR / f"{meeting_id}_transcript.json"

    if transcript_path.exists():
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript = json.load(f)

        preview_text = transcript.get("full_text", "")
        preview = preview_text[:200] + ("..." if len(preview_text) > 200 else "")

        return {
            "meeting_id": meeting_id,
            "status": "complete",
            "transcript_preview": preview,
            "full_transcript": transcript.get("full_text", ""),
            "segments": transcript.get("segments", []),
            "language": transcript.get("language", "en"),
            "summary": transcript.get("summary", "Demo summary (NLP coming soon)"),
            "tasks": [],
        }
    else:
        return {
            "meeting_id": meeting_id,
            "status": "processing",
            "message": "Transcript still being generated...",
        }


@app.get("/meeting/{meeting_id}/action-items", response_model=ActionItemsResponse)
async def get_action_items(meeting_id: str):
    """
    Return pre-extracted or on-the-fly extracted action items for a meeting.
    """
    transcript_path = UPLOADS_DIR / f"{meeting_id}_transcript.json"
    if not transcript_path.exists():
        raise HTTPException(status_code=404, detail="Transcript still being generated...")

    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    action_items_data = transcript.get("action_items", [])

    if action_items_data:
        items = [ActionItem(task=item["task"], owner=item.get("owner")) for item in action_items_data]
    else:
        full_text = transcript.get("full_text", "")
        items = extract_action_items(full_text)

    return {"items": items}


@app.get("/meeting/{meeting_id}/summary", response_model=SummaryResponse)
async def get_summary(meeting_id: str):
    """
    Return the summary stored in the transcript JSON.
    This now comes from the Ollama-based generation in process_meeting.
    """
    transcript_path = UPLOADS_DIR / f"{meeting_id}_transcript.json"
    if not transcript_path.exists():
        raise HTTPException(status_code=404, detail="Transcript still being generated...")

    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    summary = transcript.get("summary")

    if not summary:
        return {"summary": "Summary not available. Please wait for processing to complete."}

    return {"summary": summary}

# =========================
# Processing pipeline
# =========================

def process_meeting(meeting_id: str, file_path: str):
    """
    Full processing pipeline: Whisper → Transcript → Summary (via Ollama) → Action Items.
    Also optionally deletes the uploaded audio/video file after transcription to save space.
    """
    print(f"🔄 Starting processing for {meeting_id}")

    try:
        # -------------------------------------------
        # Step 1: Whisper transcription (unchanged)
        # -------------------------------------------
        transcript = transcribe_audio(file_path)
        save_transcript(meeting_id, transcript)

        # Optional: delete original uploaded file to save disk space
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Deleted original audio/video file: {file_path}")
        except Exception as e:
            print(f"⚠️ Could not delete file {file_path}: {str(e)}")

        transcript_path = UPLOADS_DIR / f"{meeting_id}_transcript.json"
        full_text = transcript.get("full_text", "")

        # -------------------------------------------
        # Step 2: Generate summary using Ollama
        # -------------------------------------------
        print(f"⏳ Generating summary for {meeting_id} using Ollama...")

        if full_text.strip():
            try:
                transcript_type = classify_transcript(full_text)
                prompt = make_summary_prompt(transcript_type, full_text)

                summary_text = run_ollama(prompt, model="phi3:mini")

                with open(transcript_path, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)

                transcript_data["type"] = transcript_type
                transcript_data["summary"] = summary_text

                with open(transcript_path, "w", encoding="utf-8") as f:
                    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

                print(f"✅ Summary generated for {meeting_id} (type={transcript_type})")

            except Exception as e:
                print(f"⚠️ Summary generation error (Ollama): {str(e)}")

                # Store a fallback summary string in JSON
                try:
                    with open(transcript_path, "r", encoding="utf-8") as f:
                        transcript_data = json.load(f)

                    transcript_data["summary"] = (
                        "Summary could not be generated automatically. "
                        "Please review the full transcript for details."
                    )

                    with open(transcript_path, "w", encoding="utf-8") as f:
                        json.dump(transcript_data, f, indent=2, ensure_ascii=False)

                    print(f"ℹ️ Stored fallback summary for {meeting_id}")
                except Exception as e2:
                    print(f"⚠️ Failed to store fallback summary: {str(e2)}")
        else:
            # If full_text is empty, also store a fallback summary
            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)

                transcript_data["summary"] = (
                    "Summary could not be generated because the transcript is empty."
                )

                with open(transcript_path, "w", encoding="utf-8") as f:
                    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

                print(f"ℹ️ Stored fallback summary for empty transcript ({meeting_id})")
            except Exception as e3:
                print(f"⚠️ Failed to store fallback summary for empty transcript: {str(e3)}")

        # -------------------------------------------
        # Step 3: Extract action items
        # -------------------------------------------
        print(f"⏳ Extracting action items for {meeting_id}...")
        try:
            action_items = extract_action_items(full_text)
            items_list = [{"task": item.task, "owner": item.owner} for item in action_items]

            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_data = json.load(f)

            if items_list:
                transcript_data["action_items"] = items_list
                print(f"✅ Action items extracted for {meeting_id} ({len(items_list)} items)")
            else:
                transcript_data.pop("action_items", None)
                print(f"ℹ️ No action items found for {meeting_id}; nothing stored.")

            with open(transcript_path, "w", encoding="utf-8") as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"⚠️ Action items extraction error: {str(e)}")

        # -------------------------------------------
        # Done
        # -------------------------------------------
        print(f"✅ {meeting_id} FULLY PROCESSED!")

    except Exception as e:
        print(f"❌ Error processing {meeting_id}: {str(e)}")
        import traceback
        traceback.print_exc()

# =========================
# Entry point
# =========================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
