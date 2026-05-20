import sys
from pathlib import Path
import numpy as np

# Get ffmpeg FIRST
try:
    import imageio_ffmpeg

    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"✅ ffmpeg executable: {FFMPEG_EXE}")
except ImportError:
    print("⚠️ imageio-ffmpeg not found!")
    FFMPEG_EXE = "ffmpeg"

# NOW import whisper
import whisper

# Add parent directory to path (so we can import config)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import WHISPER_MODEL, UPLOADS_DIR


def custom_load_audio(file: str, sr: int = 16000):
    """Load audio using imageio-ffmpeg instead of system ffmpeg"""
    import subprocess

    cmd = [
        FFMPEG_EXE,
        "-nostdin",
        "-threads",
        "0",
        "-i",
        file,
        "-f",
        "s16le",
        "-ac",
        "1",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sr),
        "-",
    ]

    try:
        out = subprocess.run(cmd, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e

    audio = np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
    return audio


# Monkey-patch Whisper's audio loader
whisper.audio.load_audio = custom_load_audio

# Load Whisper model once
model = None


def load_whisper_model():
    """Load Whisper model on first use"""
    global model
    if model is None:
        print("🔄 Loading Whisper model...")
        model = whisper.load_model(WHISPER_MODEL)
        print("✅ Whisper model loaded!")
    return model


def transcribe_audio(file_path: str) -> dict:
    """Transcribe audio file → text + segments"""
    model = load_whisper_model()

    print(f"🎤 Transcribing: {file_path}")

    result = model.transcribe(
        file_path,
        verbose=False,
        language="en",
        fp16=False,
    )

    segments = []
    for seg in result["segments"]:
        segments.append(
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
                "speaker": "Unknown",  # Placeholder, diarization later
            }
        )

    print(f"✅ Transcription complete: {len(segments)} segments")

    return {
        "full_text": result["text"],
        "segments": segments,
        "language": result.get("language", "en"),
        "duration": len(segments),
    }


def save_transcript(meeting_id: str, transcript: dict):
    """Save transcript to JSON"""
    import json

    output_path = UPLOADS_DIR / f"{meeting_id}_transcript.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)
    print(f"💾 Transcript saved: {output_path}")


def run_asr_job(meeting_id: str, audio_path: Path):
    """Run ASR job for a meeting"""
    transcript = transcribe_audio(str(audio_path))
    save_transcript(meeting_id, transcript)
