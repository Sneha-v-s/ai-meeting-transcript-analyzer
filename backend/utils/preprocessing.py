# backend/utils/preprocessing.py
from typing import Any, Dict


def postprocess_whisper_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lightweight post‑processing hook for Whisper output.
    Currently returns result as is; customize if needed.
    """
    return result
