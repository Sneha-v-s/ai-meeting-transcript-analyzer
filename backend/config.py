import os
from pathlib import Path

# Project root: .../meeting_analyzer
BASE_DIR = Path(__file__).parent.parent

UPLOADS_DIR = BASE_DIR / "uploads"
MODELS_DIR = BASE_DIR / "models"

UPLOADS_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

# Whisper model size (change to "small" or "medium" later)
WHISPER_MODEL = "medium"
