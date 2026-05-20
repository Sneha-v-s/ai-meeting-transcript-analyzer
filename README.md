# AI Meeting Transcript Analyzer

AI-powered tool to transcribe meeting audio/video using Whisper and analyze the transcript to generate summaries and action items, all running locally via FastAPI.

## Features

- Upload audio or video files (e.g. `.mp4`, `.wav`).
- Transcription using Whisper (via `workers/asr.py`).
- Stores full transcript and segments as JSON in `uploads/`.
- Generates a meeting summary (with LLM or fallback text).
- Extracts potential action items from the transcript.
- Simple web UI built with FastAPI + Jinja2 templates.

## Project structure

```text
meeting_analyzer/
├─ backend/
│  ├─ main.py            # FastAPI app and processing pipeline
│  ├─ config.py          # Paths and model configuration
│  └─ workers/
│     └─ asr.py          # Whisper transcription logic
├─ frontend/
│  ├─ templates/
│  │  └─ index.html      # Upload + analysis UI
│  └─ static/            # CSS/JS and assets
├─ uploads/              # Transcripts and (optionally) uploaded files
├─ requirements.txt
├─ project_tree.txt
└─ README.md
```

> Note: `uploads/` is where transcript JSON files like `abcd1234_transcript.json` are stored.

## Requirements

- Python 3.10+ (tested on Windows)
- Git
- (Optional) Ollama running locally if you enable LLM summaries

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the app

From the `backend` directory:

```bash
uvicorn main:app --host 0.0.0.0 --port 9000
```

Then open:

- `http://localhost:9000` in your browser.

You should see the upload page.

## How it works (end to end)

1. **Upload**  
   Select an audio/video file (e.g. `meeting.mp4`) and upload it via the UI.

2. **Processing pipeline**  
   On upload, the backend:

   - Generates a `meeting_id` (e.g. `4d5aa897`).
   - Saves the file to `uploads/{meeting_id}_filename.ext`.
   - Runs `process_meeting(meeting_id, file_path)`:
     - Transcribes the audio/video using Whisper.
     - Saves `uploads/{meeting_id}_transcript.json`.
     - (If enabled and resources allow) calls a local LLM via Ollama to generate a summary.
     - Extracts action items using keyword heuristics.
     - Updates the transcript JSON with `"summary"` and `"action_items"` fields.

3. **Viewing results**  
   The frontend fetches results from:

   - `GET /api/meeting/{meeting_id}` – transcript metadata + preview.
   - `GET /meeting/{meeting_id}/summary` – summary text.
   - `GET /meeting/{meeting_id}/action-items` – list of extracted action items.

## Example outputs

<img width="861" height="424" alt="image" src="https://github.com/user-attachments/assets/bc33eefc-19d0-4fef-b946-fe0caa1b95a1" />
<img width="864" height="432" alt="image" src="https://github.com/user-attachments/assets/1f3cab52-0daf-44af-8bbc-d265518389cb" />
<img width="864" height="426" alt="image" src="https://github.com/user-attachments/assets/9f9d75cf-4ca4-4350-b89f-1e054fdf44c9" />
<img width="868" height="428" alt="image" src="https://github.com/user-attachments/assets/d6b531b1-ea80-40ce-9b1f-1dd14a8c34c7" />
<img width="749" height="367" alt="image" src="https://github.com/user-attachments/assets/31b8112c-657e-4050-b302-974e2ec790ef" />
<img width="749" height="367" alt="image" src="https://github.com/user-attachments/assets/3dab3777-d6f6-400f-b599-d1aaaf16fba0" />

### Example transcript JSON (truncated)

```json
{
  "meeting_id": "4d5aa897",
  "full_text": "Heart beats fast, colors and promises ... Thanks for watching!",
  "segments": [
    {
      "start": 0.0,
      "end": 29.0,
      "text": "Heart beats fast, colors and promises",
      "speaker": "Unknown"
    },
    {
      "start": 29.0,
      "end": 39.0,
      "text": "How to be brave, how can I love when I'm afraid to fall",
      "speaker": "Unknown"
    },
    {
      "start": 39.0,
      "end": 44.0,
      "text": "But watching you stand alone",
      "speaker": "Unknown"
    }
  ],
  "language": "en",
  "duration": 31,
  "type": "generic",
  "summary": "In this deeply emotional and impassioned piece, the speaker expresses an unwavering... like \"heart beats fast\" and ...ht this heart closer every day without ... and resolute resolve—\"I have died ... I will be brave,\" they... affection, ... life's uncertainties with the phrase \"But watching you stand alone.\" Ultimately, it is this speaker ...love itself.",
  "action_items": []
}
```

*(Example structure only – fields may vary depending on the audio and processing.)*

### Example API usage

Get meeting metadata:

```bash
curl http://localhost:9000/api/meeting/4d5aa897
```

Get summary:

```bash
curl http://localhost:9000/meeting/4d5aa897/summary
```

Get action items:

```bash
curl http://localhost:9000/meeting/4d5aa897/action-items
```

## Notes

- On low-memory machines, LLM summary generation via Ollama may fail with 500 errors; in that case, a fallback summary string is stored instead.
- Whisper transcription can take several minutes for long recordings.

## License

This project is licensed under the MIT License.
